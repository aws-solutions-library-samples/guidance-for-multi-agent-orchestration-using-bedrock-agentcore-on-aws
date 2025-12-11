import * as cdk from 'aws-cdk-lib';
import * as bedrockagentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';
import * as fs from 'fs';
import * as path from 'path';

export interface OrderManagementAgentStackProps extends cdk.StackProps {
  orchestratorStackName: string;
  executionRoleArn: string;
  cognitoDiscoveryUrl: string;
  cognitoClientId: string;
  runtimeIdParameterName: string;
}

export class OrderManagementAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: OrderManagementAgentStackProps) {
    super(scope, id, props);

    // Import existing ECR Repository from main stack
    const repository = ecr.Repository.fromRepositoryName(
      this, 
      'OrderManagementAgentRepository', 
      'customer-support-order-management-agent'
    );

    // Build and push container image
    const orderManagementAgentImage = new ecr_assets.DockerImageAsset(this, 'OrderManagementAgentImage', {
      directory: '../agents/order-management-agent',
      platform: ecr_assets.Platform.LINUX_ARM64
    });

    // Orders Lambda
    const ordersLambda = new lambda.Function(this, 'OrdersLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../agents/order-management-agent/gateway/lambdas/orders'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256
    });

    // Inventory Lambda
    const inventoryLambda = new lambda.Function(this, 'InventoryLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../agents/order-management-agent/gateway/lambdas/inventory'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256
    });

    // Add permission for Gateway to invoke Orders Lambda
    ordersLambda.addPermission('GatewayInvokePermission', {
      principal: new iam.ArnPrincipal(props.executionRoleArn),
      action: 'lambda:InvokeFunction'
    });

    // Add permission for Gateway to invoke Inventory Lambda
    inventoryLambda.addPermission('GatewayInvokePermission', {
      principal: new iam.ArnPrincipal(props.executionRoleArn),
      action: 'lambda:InvokeFunction'
    });

    // Gateway Custom Resource Provider
    const gatewayProviderRole = new iam.Role(this, 'GatewayProviderRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        BedrockAgentCorePolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:*'
              ],
              resources: ['*']
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['iam:PassRole'],
              resources: [props.executionRoleArn]
            })
          ]
        })
      }
    });

    const gatewayProvider = new lambda.Function(this, 'GatewayProvider', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'gateway_provider.lambda_handler',
      code: lambda.Code.fromAsset('../agents/order-management-agent/infrastructure'),
      role: gatewayProviderRole,
      timeout: cdk.Duration.minutes(5)
    });

    // Load tool schemas
    const ordersToolSchemaPath = path.join(__dirname, '../../agents/order-management-agent/gateway/schemas/orders-tools.json');
    const ordersToolSchema = fs.readFileSync(ordersToolSchemaPath, 'utf8');

    const inventoryToolSchemaPath = path.join(__dirname, '../../agents/order-management-agent/gateway/schemas/inventory-tools.json');
    const inventoryToolSchema = fs.readFileSync(inventoryToolSchemaPath, 'utf8');

    // Gateway Custom Resource with targets
    const gatewayResource = new cdk.CustomResource(this, 'OrderManagementGateway', {
      serviceToken: gatewayProvider.functionArn,
      properties: {
        Version: '1.1',
        GatewayName: `order-management-gateway-${cdk.Names.uniqueId(this)}`,
        GatewayDescription: 'Gateway for Order Management Agent tools',
        GatewayRoleArn: props.executionRoleArn,
        CognitoDiscoveryUrl: props.cognitoDiscoveryUrl,
        CognitoClientId: props.cognitoClientId,
        Targets: JSON.stringify([
          {
            name: 'orders',
            lambdaArn: ordersLambda.functionArn,
            toolSchema: ordersToolSchema
          },
          {
            name: 'inventory',
            lambdaArn: inventoryLambda.functionArn,
            toolSchema: inventoryToolSchema
          }
        ])
      }
    });

    // Ensure Gateway creation waits for Lambdas
    gatewayResource.node.addDependency(ordersLambda);
    gatewayResource.node.addDependency(inventoryLambda);

    // AgentCore Runtime
    const runtime = new bedrockagentcore.CfnRuntime(this, 'OrderManagementAgentRuntime', {
      agentRuntimeName: `cust_support_${cdk.Names.uniqueId(this).substring(0, 20)}`,
      agentRuntimeArtifact: {
        containerConfiguration: {
          containerUri: orderManagementAgentImage.imageUri
        }
      },
      roleArn: props.executionRoleArn,
      networkConfiguration: {
        networkMode: 'PUBLIC'
      },
      authorizerConfiguration: {
        customJwtAuthorizer: {
          discoveryUrl: props.cognitoDiscoveryUrl,
          allowedClients: [props.cognitoClientId]
        }
      },
      // requestHeaderConfiguration not yet supported in CDK - will be added via fix_runtime_auth.py
      description: 'Customer Support Order Management Agent Runtime',
      environmentVariables: {
        LOG_LEVEL: 'INFO',
        GATEWAY_ID: gatewayResource.getAttString('GatewayId')
      }
    } as any);

    // Write runtime ID to SSM for supervisor discovery
    new ssm.StringParameter(this, 'RuntimeIdParameter', {
      parameterName: props.runtimeIdParameterName,
      stringValue: runtime.attrAgentRuntimeId,
      description: 'Runtime ID for Order Management Agent',
      tier: ssm.ParameterTier.STANDARD
    });

    // Outputs
    new cdk.CfnOutput(this, 'OrderManagementAgentRuntimeArn', {
      value: runtime.attrAgentRuntimeArn,
      description: 'ARN of the Order Management Agent Runtime'
    });

    new cdk.CfnOutput(this, 'OrderManagementAgentRuntimeId', {
      value: runtime.attrAgentRuntimeId,
      description: 'Runtime ID of the Order Management Agent'
    });

    new cdk.CfnOutput(this, 'OrderManagementAgentImageUri', {
      value: orderManagementAgentImage.imageUri,
      description: 'Container image URI for Order Management Agent'
    });

    new cdk.CfnOutput(this, 'GatewayId', {
      value: gatewayResource.getAttString('GatewayId'),
      description: 'ID of the Order Management Agent Gateway'
    });

    new cdk.CfnOutput(this, 'OrdersLambdaArn', {
      value: ordersLambda.functionArn,
      description: 'ARN of the Orders Lambda'
    });

    new cdk.CfnOutput(this, 'InventoryLambdaArn', {
      value: inventoryLambda.functionArn,
      description: 'ARN of the Inventory Lambda'
    });

    // Granular CDK-nag suppressions following PersonalizationAgentStack pattern
    // Lambda service role managed policies (Category 2: Standard AWS Patterns)
    NagSuppressions.addResourceSuppressionsByPath(this, [
      '/OrderManagementAgentStack/OrdersLambda/ServiceRole/Resource',
      '/OrderManagementAgentStack/InventoryLambda/ServiceRole/Resource'
    ], [
      { 
        id: 'AwsSolutions-IAM4', 
        reason: 'Lambda functions require AWSLambdaBasicExecutionRole for CloudWatch logging',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }
    ]);

    // Gateway provider managed policy (Category 1: CDK Deployment Infrastructure)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/OrderManagementAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM4', 
        reason: 'CDK custom resource provider requires AWSLambdaBasicExecutionRole for CloudFormation integration',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }]
    );

    // Gateway provider wildcard permissions (Category 1: CDK Deployment Infrastructure)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/OrderManagementAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'CDK custom resource provider requires broad AgentCore permissions to create gateway resources during deployment',
        appliesTo: ['Action::bedrock-agentcore:*', 'Resource::*']
      }]
    );

    // Lambda runtime suppressions
    NagSuppressions.addResourceSuppressionsByPath(this, '/OrderManagementAgentStack/OrdersLambda/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
    NagSuppressions.addResourceSuppressionsByPath(this, '/OrderManagementAgentStack/InventoryLambda/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
    NagSuppressions.addResourceSuppressionsByPath(this, '/OrderManagementAgentStack/GatewayProvider/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
  }
}