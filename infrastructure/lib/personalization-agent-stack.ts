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

export interface PersonalizationAgentStackProps extends cdk.StackProps {
  orchestratorStackName: string;
  memoryId: string;
  executionRoleArn: string;
  cognitoDiscoveryUrl: string;
  cognitoClientId: string;
  knowledgeBaseId: string;
  runtimeIdParameterName: string;
}

export class PersonalizationAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: PersonalizationAgentStackProps) {
    super(scope, id, props);

    // Import existing ECR Repository from main stack
    const repository = ecr.Repository.fromRepositoryName(
      this, 
      'PersonalizationAgentRepository', 
      'customer-support-personalization-agent'
    );

    // Build and push container image
    const personalizationAgentImage = new ecr_assets.DockerImageAsset(this, 'PersonalizationAgentImage', {
      directory: '../agents/personalization-agent',
      platform: ecr_assets.Platform.LINUX_ARM64
    });

    // Customer Database Lambda
    const customerDbLambda = new lambda.Function(this, 'CustomerDatabaseLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../agents/personalization-agent/gateway/lambdas/customer-database'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256
    });

    // Browsing Knowledge Base Lambda
    const browsingKbLambda = new lambda.Function(this, 'BrowsingKbLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../agents/personalization-agent/gateway/lambdas/browsing-kb'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        KNOWLEDGE_BASE_ID: props.knowledgeBaseId!
      }
    });

    // Add Bedrock permissions to browsing-kb Lambda
    browsingKbLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:GetKnowledgeBase',
        'bedrock:Retrieve'
      ],
      resources: [
        `arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/${props.knowledgeBaseId}`
      ]
    }));

    // Add permission for Gateway to invoke Customer Database Lambda
    customerDbLambda.addPermission('GatewayInvokePermission', {
      principal: new iam.ArnPrincipal(props.executionRoleArn),
      action: 'lambda:InvokeFunction'
    });

    // Add permission for Gateway to invoke Browsing KB Lambda
    browsingKbLambda.addPermission('GatewayInvokePermission', {
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
      code: lambda.Code.fromAsset('../agents/personalization-agent/infrastructure'),
      role: gatewayProviderRole,
      timeout: cdk.Duration.minutes(5)
    });

    // Load tool schemas
    const customerDbToolSchemaPath = path.join(__dirname, '../../agents/personalization-agent/gateway/schemas/customer-database-tools.json');
    const customerDbToolSchema = fs.readFileSync(customerDbToolSchemaPath, 'utf8');

    const browsingKbToolSchemaPath = path.join(__dirname, '../../agents/personalization-agent/gateway/schemas/browsing-kb-tools.json');
    const browsingKbToolSchema = fs.readFileSync(browsingKbToolSchemaPath, 'utf8');

    // Single Gateway Custom Resource with multiple targets
    const gatewayResource = new cdk.CustomResource(this, 'PersonalizationGateway', {
      serviceToken: gatewayProvider.functionArn,
      properties: {
        Version: '1.1', // Force update to trigger debug logging
        GatewayName: `personalization-gateway-${cdk.Names.uniqueId(this)}`,
        GatewayDescription: 'Gateway for Personalization Agent tools - debug v2',
        GatewayRoleArn: props.executionRoleArn,
        CognitoDiscoveryUrl: props.cognitoDiscoveryUrl,
        CognitoClientId: props.cognitoClientId,
        Targets: JSON.stringify([
          {
            name: 'customer-database',
            lambdaArn: customerDbLambda.functionArn,
            toolSchema: customerDbToolSchema
          },
          {
            name: 'browsing-kb',
            lambdaArn: browsingKbLambda.functionArn,
            toolSchema: browsingKbToolSchema
          }
        ])
      }
    });

    // Ensure Gateway creation waits for Lambdas
    gatewayResource.node.addDependency(customerDbLambda);
    gatewayResource.node.addDependency(browsingKbLambda);

    // AgentCore Runtime
    const runtime = new bedrockagentcore.CfnRuntime(this, 'PersonalizationAgentRuntime', {
      agentRuntimeName: `cust_support_${cdk.Names.uniqueId(this).substring(0, 20)}`,
      agentRuntimeArtifact: {
        containerConfiguration: {
          containerUri: personalizationAgentImage.imageUri
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
      // NOTE: requestHeaderConfiguration is not yet implemented in CDK
      // The Authorization header allowlist must be added manually after deployment using:
      // ./infrastructure/fix-agent-runtime.sh
      requestHeaderConfiguration: {
        requestHeaderAllowlist: ['Authorization']
      },
      description: 'Customer Support Personalization Agent Runtime',
      environmentVariables: {
        LOG_LEVEL: 'DEBUG',
        GATEWAY_ID: gatewayResource.getAttString('GatewayId'),
        MEMORY_ID: props.memoryId
      }
    } as any);

    // Write runtime ID to SSM for supervisor discovery
    new ssm.StringParameter(this, 'RuntimeIdParameter', {
      parameterName: props.runtimeIdParameterName,
      stringValue: runtime.attrAgentRuntimeId,
      description: 'Runtime ID for Personalization Agent',
      tier: ssm.ParameterTier.STANDARD
    });

    // Outputs
    new cdk.CfnOutput(this, 'PersonalizationAgentRuntimeArn', {
      value: runtime.attrAgentRuntimeArn,
      description: 'ARN of the Personalization Agent Runtime',
      exportName: 'PersonalizationAgentStack-PersonalizationRuntimeArn'
    });

    new cdk.CfnOutput(this, 'PersonalizationAgentRuntimeId', {
      value: runtime.attrAgentRuntimeId,
      description: 'Runtime ID of the Personalization Agent'
    });

    new cdk.CfnOutput(this, 'PersonalizationAgentImageUri', {
      value: personalizationAgentImage.imageUri,
      description: 'Container image URI for Personalization Agent'
    });

    new cdk.CfnOutput(this, 'GatewayId', {
      value: gatewayResource.getAttString('GatewayId'),
      description: 'ID of the Personalization Agent Gateway'
    });

    new cdk.CfnOutput(this, 'BrowsingKbLambdaArn', {
      value: browsingKbLambda.functionArn,
      description: 'ARN of the Browsing Knowledge Base Lambda'
    });

    new cdk.CfnOutput(this, 'CustomerDatabaseLambdaArn', {
      value: customerDbLambda.functionArn,
      description: 'ARN of the Customer Database Lambda'
    });

    // Granular CDK-nag suppressions targeting specific policies to avoid catching unintended violations
    // Gateway provider managed policy (IAM4)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/PersonalizationAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM4', 
        reason: 'CDK custom resource provider requires AWSLambdaBasicExecutionRole for CloudFormation integration',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }]
    );

    // Gateway provider inline policy (IAM5) 
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/PersonalizationAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'CDK custom resource provider requires broad AgentCore permissions to create gateway resources during deployment',
        appliesTo: ['Action::bedrock-agentcore:*', 'Resource::*']
      }]
    );

    // Suppress Lambda service role managed policies (standard CDK pattern)
    NagSuppressions.addResourceSuppressionsByPath(this, [
      '/PersonalizationAgentStack/CustomerDatabaseLambda/ServiceRole',
      '/PersonalizationAgentStack/BrowsingKbLambda/ServiceRole'
    ], [
      { id: 'AwsSolutions-IAM4', reason: 'Lambda functions require AWSLambdaBasicExecutionRole for CloudWatch logging' }
    ]);

    // Lambda runtime suppressions
    NagSuppressions.addResourceSuppressionsByPath(this, '/PersonalizationAgentStack/CustomerDatabaseLambda/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
    NagSuppressions.addResourceSuppressionsByPath(this, '/PersonalizationAgentStack/BrowsingKbLambda/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
    NagSuppressions.addResourceSuppressionsByPath(this, '/PersonalizationAgentStack/GatewayProvider/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
  }
}
