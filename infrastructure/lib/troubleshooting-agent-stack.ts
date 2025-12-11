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

export interface TroubleshootingAgentStackProps extends cdk.StackProps {
  orchestratorStackName: string;
  memoryId: string;
  executionRoleArn: string;
  cognitoDiscoveryUrl: string;
  cognitoClientId: string;
  knowledgeBaseId: string;
  runtimeIdParameterName: string;
}

export class TroubleshootingAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: TroubleshootingAgentStackProps) {
    super(scope, id, props);

    // Import existing ECR Repository from main stack
    const repository = ecr.Repository.fromRepositoryName(
      this, 
      'TroubleshootingAgentRepository', 
      'customer-support-troubleshooting-agent'
    );

    // Build and push container image
    const troubleshootingAgentImage = new ecr_assets.DockerImageAsset(this, 'TroubleshootingAgentImage', {
      directory: '../agents/troubleshooting-agent',
      platform: ecr_assets.Platform.LINUX_ARM64
    });

    // KB Query Lambda
    const kbQueryLambda = new lambda.Function(this, 'KbQueryLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../agents/troubleshooting-agent/gateway/lambdas/kb-query'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        KNOWLEDGE_BASE_ID: props.knowledgeBaseId!
      }
    });

    // Add Bedrock permissions to kb-query Lambda
    kbQueryLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:GetKnowledgeBase',
        'bedrock:Retrieve'
      ],
      resources: [
        `arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/${props.knowledgeBaseId}`
      ]
    }));

    // Add permission for Gateway to invoke KB Query Lambda
    kbQueryLambda.addPermission('GatewayInvokePermission', {
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
      code: lambda.Code.fromAsset('../agents/troubleshooting-agent/infrastructure'),
      role: gatewayProviderRole,
      timeout: cdk.Duration.minutes(5)
    });

    // Load tool schema
    const kbQueryToolSchemaPath = path.join(__dirname, '../../agents/troubleshooting-agent/gateway/schemas/kb-query-tools.json');
    const kbQueryToolSchema = fs.readFileSync(kbQueryToolSchemaPath, 'utf8');

    // Gateway Custom Resource with kb-query target
    const gatewayResource = new cdk.CustomResource(this, 'TroubleshootingGateway', {
      serviceToken: gatewayProvider.functionArn,
      properties: {
        Version: '1.1',
        GatewayName: `troubleshooting-gateway-${cdk.Names.uniqueId(this)}`,
        GatewayDescription: 'Gateway for Troubleshooting Agent tools',
        GatewayRoleArn: props.executionRoleArn,
        CognitoDiscoveryUrl: props.cognitoDiscoveryUrl,
        CognitoClientId: props.cognitoClientId,
        Targets: JSON.stringify([
          {
            name: 'kb-query',
            lambdaArn: kbQueryLambda.functionArn,
            toolSchema: kbQueryToolSchema
          }
        ])
      }
    });

    // Ensure Gateway creation waits for Lambda
    gatewayResource.node.addDependency(kbQueryLambda);

    // AgentCore Runtime
    const runtime = new bedrockagentcore.CfnRuntime(this, 'TroubleshootingAgentRuntime', {
      agentRuntimeName: `cust_support_${cdk.Names.uniqueId(this).substring(0, 20)}`,
      agentRuntimeArtifact: {
        containerConfiguration: {
          containerUri: troubleshootingAgentImage.imageUri
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
      description: 'Customer Support Troubleshooting Agent Runtime',
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
      description: 'Runtime ID for Troubleshooting Agent',
      tier: ssm.ParameterTier.STANDARD
    });

    // Outputs
    new cdk.CfnOutput(this, 'TroubleshootingAgentRuntimeArn', {
      value: runtime.attrAgentRuntimeArn,
      description: 'ARN of the Troubleshooting Agent Runtime',
      exportName: 'TroubleshootingAgentStack-TroubleshootingRuntimeArn'
    });

    new cdk.CfnOutput(this, 'TroubleshootingAgentRuntimeId', {
      value: runtime.attrAgentRuntimeId,
      description: 'Runtime ID of the Troubleshooting Agent'
    });

    new cdk.CfnOutput(this, 'TroubleshootingAgentImageUri', {
      value: troubleshootingAgentImage.imageUri,
      description: 'Container image URI for Troubleshooting Agent'
    });

    new cdk.CfnOutput(this, 'GatewayId', {
      value: gatewayResource.getAttString('GatewayId'),
      description: 'ID of the Troubleshooting Agent Gateway'
    });

    new cdk.CfnOutput(this, 'KbQueryLambdaArn', {
      value: kbQueryLambda.functionArn,
      description: 'ARN of the KB Query Lambda'
    });

    // Granular CDK-nag suppressions following established pattern
    // Lambda service role managed policy (Category 2: Standard AWS Patterns)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/TroubleshootingAgentStack/KbQueryLambda/ServiceRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM4', 
        reason: 'Lambda functions require AWSLambdaBasicExecutionRole for CloudWatch logging',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }]
    );

    // Gateway provider managed policy (Category 1: CDK Deployment Infrastructure)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/TroubleshootingAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM4', 
        reason: 'CDK custom resource provider requires AWSLambdaBasicExecutionRole for CloudFormation integration',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }]
    );

    // Gateway provider wildcard permissions (Category 1: CDK Deployment Infrastructure)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/TroubleshootingAgentStack/GatewayProviderRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'CDK custom resource provider requires broad AgentCore permissions to create gateway resources during deployment',
        appliesTo: ['Action::bedrock-agentcore:*', 'Resource::*']
      }]
    );

    // Lambda runtime suppressions
    NagSuppressions.addResourceSuppressionsByPath(this, '/TroubleshootingAgentStack/KbQueryLambda/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
    NagSuppressions.addResourceSuppressionsByPath(this, '/TroubleshootingAgentStack/GatewayProvider/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]);
  }
}
