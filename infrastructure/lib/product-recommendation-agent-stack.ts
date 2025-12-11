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

export interface ProductRecommendationAgentStackProps extends cdk.StackProps {
  orchestratorStackName: string;
  memoryId: string;
  executionRoleArn: string;
  cognitoDiscoveryUrl: string;
  cognitoClientId: string;
  runtimeIdParameterName: string;
}

export class ProductRecommendationAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ProductRecommendationAgentStackProps) {
    super(scope, id, props);

    // Import existing ECR Repository from main stack
    const repository = ecr.Repository.fromRepositoryName(
      this, 
      'ProductRecommendationAgentRepository', 
      'customer-support-product-recommendation-agent'
    );

    // Create Sponsored Products Lambda
    const sponsoredProductsLambda = new lambda.Function(this, 'SponsoredProductsLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../agents/product-recommendation-agent/gateway/lambdas/sponsored-products'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      environment: {
        LOG_LEVEL: 'INFO'
      }
    });

    // Create Organic Products Lambda
    const organicProductsLambda = new lambda.Function(this, 'OrganicProductsLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../agents/product-recommendation-agent/gateway/lambdas/organic-products'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      environment: {
        LOG_LEVEL: 'INFO'
      }
    });

    // Add permission for Gateway to invoke Sponsored Products Lambda
    sponsoredProductsLambda.addPermission('GatewayInvokePermission', {
      principal: new iam.ArnPrincipal(props.executionRoleArn),
      action: 'lambda:InvokeFunction'
    });

    // Add permission for Gateway to invoke Organic Products Lambda
    organicProductsLambda.addPermission('GatewayInvokePermission', {
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
      code: lambda.Code.fromAsset('../agents/product-recommendation-agent/gateway/infrastructure'),
      role: gatewayProviderRole,
      timeout: cdk.Duration.minutes(5)
    });

    // Load tool schemas
    const sponsoredToolSchemaPath = path.join(__dirname, '../../agents/product-recommendation-agent/gateway/schemas/sponsored-products-tools.json');
    const sponsoredToolSchema = fs.readFileSync(sponsoredToolSchemaPath, 'utf8');

    const organicToolSchemaPath = path.join(__dirname, '../../agents/product-recommendation-agent/gateway/schemas/organic-products-tools.json');
    const organicToolSchema = fs.readFileSync(organicToolSchemaPath, 'utf8');

    // Create Sponsored Products Gateway (Gateway 1 → Target 1 → Lambda 1)
    const sponsoredGatewayResource = new cdk.CustomResource(this, 'SponsoredProductsGateway', {
      serviceToken: gatewayProvider.functionArn,
      properties: {
        Version: '1.0',
        GatewayName: `sponsored-products-gw`,
        GatewayDescription: 'Gateway for Sponsored Products tools',
        GatewayRoleArn: props.executionRoleArn,
        CognitoDiscoveryUrl: props.cognitoDiscoveryUrl,
        CognitoClientId: props.cognitoClientId,
        Targets: JSON.stringify([
          {
            name: 'sponsored-products',
            lambdaArn: sponsoredProductsLambda.functionArn,
            toolSchema: sponsoredToolSchema
          }
        ])
      }
    });

    // Ensure Sponsored Gateway creation waits for Lambda
    sponsoredGatewayResource.node.addDependency(sponsoredProductsLambda);

    // Create Organic Products Gateway (Gateway 2 → Target 1 → Lambda 2)
    const organicGatewayResource = new cdk.CustomResource(this, 'OrganicProductsGateway', {
      serviceToken: gatewayProvider.functionArn,
      properties: {
        Version: '1.0',
        GatewayName: `organic-products-gw`,
        GatewayDescription: 'Gateway for Organic Products tools',
        GatewayRoleArn: props.executionRoleArn,
        CognitoDiscoveryUrl: props.cognitoDiscoveryUrl,
        CognitoClientId: props.cognitoClientId,
        Targets: JSON.stringify([
          {
            name: 'organic-products',
            lambdaArn: organicProductsLambda.functionArn,
            toolSchema: organicToolSchema
          }
        ])
      }
    });

    // Ensure Organic Gateway creation waits for Lambda
    organicGatewayResource.node.addDependency(organicProductsLambda);

    // Build and push agent container image
    const productRecommendationAgentImage = new ecr_assets.DockerImageAsset(this, 'ProductRecommendationAgentImage', {
      directory: '../agents/product-recommendation-agent',
      file: 'Dockerfile',
      platform: ecr_assets.Platform.LINUX_ARM64
    });

    // Create AgentCore Runtime
    const runtime = new bedrockagentcore.CfnRuntime(this, 'ProductRecommendationAgentRuntime', {
      agentRuntimeName: `cust_support_${cdk.Names.uniqueId(this).substring(0, 20)}`,
      agentRuntimeArtifact: {
        containerConfiguration: {
          containerUri: productRecommendationAgentImage.imageUri
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
      requestHeaderConfiguration: {
        requestHeaderAllowlist: ['Authorization']
      },
      description: 'Product Recommendation Agent Runtime',
      environmentVariables: {
        SPONSORED_GATEWAY_ID: sponsoredGatewayResource.getAttString('GatewayId'),
        ORGANIC_GATEWAY_ID: organicGatewayResource.getAttString('GatewayId'),
        MEMORY_ID: props.memoryId,
        LOG_LEVEL: 'INFO',
        AWS_REGION: this.region,
        PYTHONUNBUFFERED: '1'
      }
    } as any);

    // Write runtime ID to SSM for supervisor discovery
    new ssm.StringParameter(this, 'RuntimeIdParameter', {
      parameterName: props.runtimeIdParameterName,
      stringValue: runtime.attrAgentRuntimeId,
      description: 'Runtime ID for Product Recommendation Agent',
      tier: ssm.ParameterTier.STANDARD
    });

    // Outputs
    new cdk.CfnOutput(this, 'ProductRecommendationAgentRuntimeArn', {
      value: runtime.attrAgentRuntimeArn,
      description: 'ARN of the Product Recommendation Agent Runtime',
      exportName: 'ProductRecommendationAgentStack-RuntimeArn'
    });

    new cdk.CfnOutput(this, 'ProductRecommendationAgentRuntimeId', {
      value: runtime.attrAgentRuntimeId,
      description: 'Runtime ID of the Product Recommendation Agent'
    });

    new cdk.CfnOutput(this, 'ProductRecommendationAgentImageUri', {
      value: productRecommendationAgentImage.imageUri,
      description: 'Container image URI for Product Recommendation Agent'
    });

    new cdk.CfnOutput(this, 'SponsoredGatewayId', {
      value: sponsoredGatewayResource.getAttString('GatewayId'),
      description: 'ID of the Sponsored Products Gateway'
    });

    new cdk.CfnOutput(this, 'OrganicGatewayId', {
      value: organicGatewayResource.getAttString('GatewayId'),
      description: 'ID of the Organic Products Gateway'
    });

    new cdk.CfnOutput(this, 'SponsoredProductsLambdaArn', {
      value: sponsoredProductsLambda.functionArn,
      description: 'ARN of the Sponsored Products Lambda'
    });

    new cdk.CfnOutput(this, 'OrganicProductsLambdaArn', {
      value: organicProductsLambda.functionArn,
      description: 'ARN of the Organic Products Lambda'
    });

    // Granular CDK-nag suppressions following established pattern
    // Lambda service role managed policies (Category 2: Standard AWS Patterns)
    NagSuppressions.addResourceSuppressionsByPath(this, [
      '/ProductRecommendationAgentStack/SponsoredProductsLambda/ServiceRole/Resource',
      '/ProductRecommendationAgentStack/OrganicProductsLambda/ServiceRole/Resource'
    ], [
      { 
        id: 'AwsSolutions-IAM4', 
        reason: 'Lambda functions require AWSLambdaBasicExecutionRole for CloudWatch logging',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }
    ]);

    // Gateway provider managed policy (Category 1: CDK Deployment Infrastructure)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/ProductRecommendationAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM4', 
        reason: 'CDK custom resource provider requires AWSLambdaBasicExecutionRole for CloudFormation integration',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }]
    );

    // Gateway provider wildcard permissions (Category 1: CDK Deployment Infrastructure)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/ProductRecommendationAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'CDK custom resource provider requires broad AgentCore permissions to create gateway resources during deployment',
        appliesTo: ['Action::bedrock-agentcore:*', 'Resource::*']
      }]
    );

    // Lambda runtime suppressions
    NagSuppressions.addResourceSuppressionsByPath(this, '/ProductRecommendationAgentStack/SponsoredProductsLambda/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
    NagSuppressions.addResourceSuppressionsByPath(this, '/ProductRecommendationAgentStack/OrganicProductsLambda/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
    NagSuppressions.addResourceSuppressionsByPath(this, '/ProductRecommendationAgentStack/GatewayProvider/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
  }
}
