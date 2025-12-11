import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as bedrockagentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { NagSuppressions } from 'cdk-nag';

import { Construct } from 'constructs';

export class CustomerSupportAssistantStack extends cdk.Stack {
  public get orderManagementRuntimeIdParameterName(): string {
    return `/${this.stackName}/order-management-agent/runtime-id`;
  }

  public get personalizationRuntimeIdParameterName(): string {
    return `/${this.stackName}/personalization-agent/runtime-id`;
  }

  public get productRecommendationRuntimeIdParameterName(): string {
    return `/${this.stackName}/product-recommendation-agent/runtime-id`;
  }

  public get troubleshootingRuntimeIdParameterName(): string {
    return `/${this.stackName}/troubleshooting-agent/runtime-id`;
  }

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ECR Repositories for agent containers
    const supervisorRepository = new ecr.Repository(this, 'SupervisorAgentRepository', {
      repositoryName: 'customer-support-supervisor-agent',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      lifecycleRules: [{
        maxImageCount: 10,
        description: 'Keep only 10 most recent images'
      }]
    });

    const orderManagementRepository = new ecr.Repository(this, 'OrderManagementAgentRepository', {
      repositoryName: 'customer-support-order-management-agent',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      lifecycleRules: [{
        maxImageCount: 10,
        description: 'Keep only 10 most recent images'
      }]
    });

    const productRecommendationRepository = new ecr.Repository(this, 'ProductRecommendationAgentRepository', {
      repositoryName: 'customer-support-product-recommendation-agent',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      lifecycleRules: [{
        maxImageCount: 10,
        description: 'Keep only 10 most recent images'
      }]
    });

    const personalizationRepository = new ecr.Repository(this, 'PersonalizationAgentRepository', {
      repositoryName: 'customer-support-personalization-agent',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      lifecycleRules: [{
        maxImageCount: 10,
        description: 'Keep only 10 most recent images'
      }]
    });

    const troubleshootingRepository = new ecr.Repository(this, 'TroubleshootingAgentRepository', {
      repositoryName: 'customer-support-troubleshooting-agent',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      lifecycleRules: [{
        maxImageCount: 10,
        description: 'Keep only 10 most recent images'
      }]
    });

    // Cognito User Pool for Authentication
    const userPool = new cognito.UserPool(this, 'CustomerSupportUserPool', {
      userPoolName: 'customer-support-users',
      signInAliases: {
        email: true,
        username: false
      },
      passwordPolicy: {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true
      },
      mfa: cognito.Mfa.OPTIONAL,
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      selfSignUpEnabled: true,
      userVerification: {
        emailSubject: 'Customer Support - Verify your account',
        emailBody: 'Please verify your account by clicking {##Verify Email##}',
        emailStyle: cognito.VerificationEmailStyle.LINK
      },
      customAttributes: {
        'customer_id': new cognito.StringAttribute({ 
          minLen: 1, 
          maxLen: 256,
          mutable: true 
        })
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY // For development/testing
    });

    // Cognito User Pool Client for JWT token issuance
    const userPoolClient = new cognito.UserPoolClient(this, 'CustomerSupportClient', {
      userPool: userPool,
      userPoolClientName: 'customer-support-client',
      generateSecret: false, // Public client for web applications
      authFlows: {
        userSrp: true,
        userPassword: true, // Enable for OAuth testing as per AWS docs
        adminUserPassword: true // Enable for testing purposes
      },
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: false // More secure flow
        },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE
        ],
        callbackUrls: ['https://localhost:3000/callback'], // Will be updated for production
        logoutUrls: ['https://localhost:3000/logout']
      },
      readAttributes: new cognito.ClientAttributes()
        .withStandardAttributes({ email: true, emailVerified: true })
        .withCustomAttributes('customer_id'),
      idTokenValidity: cdk.Duration.hours(1),
      accessTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      preventUserExistenceErrors: true // Security best practice
    });

    // Cognito User Pool Domain for hosted UI
    const userPoolDomain = new cognito.UserPoolDomain(this, 'CustomerSupportDomain', {
      userPool: userPool,
      cognitoDomain: {
        // Use simple CloudFormation tokens (no complex functions)
        domainPrefix: `customer-support-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`
      }
    });

    // Configuration will be hardcoded in Lambda functions - no Parameter Store needed

    // IAM Role for Memory Management Lambda - CORRECTED PERMISSIONS
    const memoryManagerRole = new iam.Role(this, 'MemoryManagerRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for Customer Support Memory Manager Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        BedrockAgentCoreControlAccess: new iam.PolicyDocument({
          statements: [
            // Specific AgentCore Memory control plane permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:CreateMemory',
                'bedrock-agentcore:DeleteMemory',
                'bedrock-agentcore:GetMemory',
                'bedrock-agentcore:ListMemories',
                'bedrock-agentcore:UpdateMemory'
              ],
              resources: ['*'] // Memory resources don't exist until created, wildcard required
            })
          ]
        }),
        CloudWatchLogsAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
                'logs:DescribeLogGroups',
                'logs:DescribeLogStreams'
              ],
              resources: [
                `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/lambda/CustomerSupportAssistantStack-MemoryManagerFunction*`
              ]
            })
          ]
        })
      }
    });

    // Simple Lambda Function for Memory Management (matching DeepResearchAgent pattern)
    const memoryManagerFunction = new lambda.Function(this, 'MemoryManagerFunction', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../lambda/memory-manager'),
      role: memoryManagerRole,
      timeout: cdk.Duration.minutes(10), // Increased timeout for memory creation
      memorySize: 512, // Standard memory
      architecture: lambda.Architecture.ARM_64, // Use ARM64 to match our dependencies
      environment: {
        PYTHONPATH: '/opt/python'
      },
      description: 'ARM64 Lambda with corrected bedrock-agentcore-control permissions for Memory management',
      logGroup: new logs.LogGroup(this, 'MemoryManagerFunctionLogGroup', {
        retention: logs.RetentionDays.ONE_DAY,
        removalPolicy: cdk.RemovalPolicy.DESTROY
      })
    });

    // Custom Resource for AgentCore Memory - ENABLED FOR TASK 7.3 TESTING
    const memoryCustomResource = new cdk.CustomResource(this, 'CustomerSupportMemoryResource', {
      serviceToken: memoryManagerFunction.functionArn,
      properties: {
        // Static properties to avoid unnecessary replacements
        MemoryName: 'customer_support_memory',
        Description: 'Customer support conversation memory with semantic, summary, and user preference strategies',
        EventExpiryDays: '60'
      }
    });

    // Output memory resource info
    new cdk.CfnOutput(this, 'MemoryCustomResourceId', {
      value: memoryCustomResource.ref,
      description: 'Custom Resource ID for AgentCore Memory'
    });

    new cdk.CfnOutput(this, 'MemoryId', {
      value: memoryCustomResource.getAttString('MemoryId'),
      description: 'AgentCore Memory ID created by custom resource',
      exportName: 'CustomerSupportAssistantStack-MemoryId'
    });

    // IAM Role for AgentCore execution with Bedrock and Memory access - MOVED AFTER MEMORY CREATION
    const agentExecutionRole = new iam.Role(this, 'CustomerSupportAgentExecutionRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      description: 'Execution role for Customer Support AgentCore agents',
      inlinePolicies: {
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream',
                'bedrock:GetFoundationModel',
                'bedrock:ListFoundationModels'
              ],
              resources: [
                `arn:aws:bedrock:${this.region}::foundation-model/*`,
                `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
                `arn:aws:bedrock:*::foundation-model/*`
              ]
            })
          ]
        }),
        AgentCoreMemoryAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:CreateMemorySession',
                'bedrock:DeleteMemorySession',
                'bedrock:GetMemorySession',
                'bedrock:ListMemorySessions',
                'bedrock:PutMemoryEvents',
                'bedrock:GetMemoryEvents',
                'bedrock:QueryMemory',
                // AgentCore Memory Data Plane permissions
                'bedrock-agentcore:CreateEvent',
                'bedrock-agentcore:DeleteEvent',
                'bedrock-agentcore:GetEvent',
                'bedrock-agentcore:ListEvents',
                'bedrock-agentcore:DeleteMemoryRecord',
                'bedrock-agentcore:GetMemoryRecord',
                'bedrock-agentcore:ListMemoryRecords',
                'bedrock-agentcore:RetrieveMemoryRecords',
                'bedrock-agentcore:ListActors',
                'bedrock-agentcore:ListSessions'
              ],
              resources: [
                `arn:aws:bedrock:${this.region}:${this.account}:memory/${memoryCustomResource.getAttString('MemoryId')}`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:memory/${memoryCustomResource.getAttString('MemoryId')}`
              ]
            })
          ]
        }),
        AgentCoreWorkloadIdentityAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:GetWorkloadAccessToken',
                'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
                'bedrock-agentcore:GetWorkloadAccessTokenForUserId'
              ],
              resources: [
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/*`
              ]
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:InvokeAgentRuntime'
              ],
              resources: [
                // Allow invocation of customer support agent runtimes only
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:agent-runtime/cust_support_*`
              ]
            })
          ]
        }),
        CloudWatchLogs: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
              ],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:*`]
            })
          ]
        }),
        CognitoAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'cognito-idp:AdminGetUser'
              ],
              resources: [userPool.userPoolArn]
            })
          ]
        }),
        OpenTelemetryAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords'
              ],
              resources: ['*']
            })
          ]
        }),
        ECRAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ecr:GetAuthorizationToken',
                'ecr:BatchCheckLayerAvailability',
                'ecr:GetDownloadUrlForLayer',
                'ecr:BatchGetImage'
              ],
              resources: [
                `arn:aws:ecr:${this.region}:${this.account}:repository/*`
              ]
            }),
            // GetAuthorizationToken requires * resource
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ecr:GetAuthorizationToken'
              ],
              resources: ['*']
            })
          ]
        }),
        SSMParameterAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ssm:GetParameter',
                'ssm:GetParameters'
              ],
              resources: [
                `arn:aws:ssm:${this.region}:${this.account}:parameter/${this.stackName}/*`
              ]
            })
          ]
        })
      }
    });

    // CDK-nag suppressions
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/MemoryManagerFunction/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'Lambda runtime version is explicitly set to latest Python 3.13' }]
    );

    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/CustomerSupportAgentExecutionRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'Legitimate wildcards in inline policies: Bedrock models for experimentation, agent runtime scoped to cust_support_ prefix, CloudWatch logs scoped to AgentCore runtimes, workload identity scoped to directory, ECR repositories scoped to account, SSM parameters scoped to stack, X-Ray tracing and ECR GetAuthorizationToken require * per AWS service requirements',
        appliesTo: [
          'Resource::arn:aws:bedrock:<AWS::Region>::foundation-model/*',
          'Resource::arn:aws:bedrock:*::foundation-model/*',
          'Resource::arn:aws:bedrock:*:<AWS::AccountId>:inference-profile/*',
          'Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:agent-runtime/cust_support_*',
          'Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/bedrock-agentcore/runtimes/*:*',
          'Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:workload-identity-directory/default/workload-identity/*',
          'Resource::arn:aws:ecr:<AWS::Region>:<AWS::AccountId>:repository/*',
          'Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/CustomerSupportAssistantStack/*',
          'Action::xray:PutTraceSegments',
          'Action::xray:PutTelemetryRecords', 
          'Action::ecr:GetAuthorizationToken'
        ]
      }]
    );

    // Build and push supervisor agent container to ECR
    const supervisorAgentImage = new ecr_assets.DockerImageAsset(this, 'SupervisorAgentImage', {
      directory: '../agents/supervisor-agent',
      platform: ecr_assets.Platform.LINUX_ARM64, // AgentCore requires ARM64
    });


    // Define agent runtime name for consistent use across resources
    const agentRuntimeName = 'customer_support_supervisor';

    // Define parameter names for consistent use
    const personalizationRuntimeIdParameterName = `/${this.stackName}/personalization-agent/runtime-id`;
    const orderManagementRuntimeIdParameterName = `/${this.stackName}/order-management-agent/runtime-id`;
    const productRecommendationRuntimeIdParameterName = `/${this.stackName}/product-recommendation-agent/runtime-id`;
    const troubleshootingRuntimeIdParameterName = `/${this.stackName}/troubleshooting-agent/runtime-id`;

    // Shared workload name parameter used by all agent client tools
    const workloadNameParameter = new ssm.StringParameter(this, 'AgentWorkloadNameParameter', {
      parameterName: `/${this.stackName}/agent-workload-name`,
      stringValue: agentRuntimeName, // Supervisor agent's workload identity
      description: 'Workload name for Customer Support supervisor agent',
      tier: ssm.ParameterTier.STANDARD
    });

    // Native L1 Construct for Supervisor Agent Runtime - MIGRATED FROM CUSTOM RESOURCE
    const supervisorAgentRuntime = new bedrockagentcore.CfnRuntime(this, 'SupervisorAgentRuntime', {
      agentRuntimeName: agentRuntimeName,
      agentRuntimeArtifact: {
        containerConfiguration: {
          containerUri: supervisorAgentImage.imageUri
        }
      },
      roleArn: agentExecutionRole.roleArn,
      description: 'Customer Support Supervisor Agent Runtime with Cognito JWT Authentication',
      networkConfiguration: {
        networkMode: 'PUBLIC'
      },
      // JWT Authentication Configuration using Cognito as OIDC provider
      authorizerConfiguration: {
        customJwtAuthorizer: {
          discoveryUrl: `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`,
          allowedClients: [userPoolClient.userPoolClientId]
        }
      },
      // Environment variables for agent-to-agent communication
      environmentVariables: {
        LOG_LEVEL: 'DEBUG',  // Set to DEBUG for detailed logging
        MEMORY_ID: memoryCustomResource.getAttString('MemoryId'),
        AGENT_WORKLOAD_NAME: agentRuntimeName,
        ORCHESTRATOR_STACK_NAME: this.stackName,
        AWS_REGION: this.region,
        USER_POOL_ID: userPool.userPoolId,
        // SSM Parameter names for subagent runtime IDs
        PERSONALIZATION_AGENT_RUNTIME_ID_PARAM: personalizationRuntimeIdParameterName,
        ORDER_MANAGEMENT_AGENT_RUNTIME_ID_PARAM: orderManagementRuntimeIdParameterName,
        PRODUCT_RECOMMENDATION_AGENT_RUNTIME_ID_PARAM: productRecommendationRuntimeIdParameterName,
        TROUBLESHOOTING_AGENT_RUNTIME_ID_PARAM: troubleshootingRuntimeIdParameterName,
        // Force Python to use unbuffered output for immediate CloudWatch logging
        PYTHONUNBUFFERED: '1'
      }
    });

    // NOTE: RequestHeaderConfiguration is not yet supported in the CloudFormation schema
    // The JWT token will be available in the authentication context instead
    // The agent code should extract user_id from context.authentication or context.user_id

    // Ensure proper dependencies between L1 runtime construct and memory custom resource
    // The agent runtime depends on memory being available for conversation context
    supervisorAgentRuntime.node.addDependency(memoryCustomResource);

    // Ensure the agent runtime is created after the execution role is ready
    supervisorAgentRuntime.node.addDependency(agentExecutionRole);

    // Ensure the agent runtime is created after the container image is built and pushed
    supervisorAgentRuntime.node.addDependency(supervisorAgentImage);

    // Grant the agent execution role permission to read workload name parameter
    workloadNameParameter.grantRead(agentExecutionRole);

    // Outputs for ECR repository URIs
    new cdk.CfnOutput(this, 'SupervisorRepositoryURI', {
      value: supervisorRepository.repositoryUri,
      description: 'ECR Repository URI for Supervisor Agent'
    });

    new cdk.CfnOutput(this, 'OrderManagementRepositoryURI', {
      value: orderManagementRepository.repositoryUri,
      description: 'ECR Repository URI for Order Management Agent'
    });

    new cdk.CfnOutput(this, 'ProductRecommendationRepositoryURI', {
      value: productRecommendationRepository.repositoryUri,
      description: 'ECR Repository URI for Product Recommendation Agent'
    });

    new cdk.CfnOutput(this, 'PersonalizationRepositoryURI', {
      value: personalizationRepository.repositoryUri,
      description: 'ECR Repository URI for Personalization Agent'
    });

    new cdk.CfnOutput(this, 'TroubleshootingRepositoryURI', {
      value: troubleshootingRepository.repositoryUri,
      description: 'ECR Repository URI for Troubleshooting Agent'
    });

    // Output the execution role ARN
    new cdk.CfnOutput(this, 'AgentExecutionRoleArn', {
      value: agentExecutionRole.roleArn,
      description: 'Execution Role ARN for Customer Support Agents',
      exportName: 'CustomerSupportAssistantStack-AgentExecutionRoleArn'
    });

    // Memory Manager Lambda error alarm
    new cloudwatch.Alarm(this, 'MemoryManagerErrorAlarm', {
      alarmName: 'customer-support-memory-manager-errors',
      alarmDescription: 'Alert when memory manager function has errors',
      metric: memoryManagerFunction.metricErrors({
        period: cdk.Duration.minutes(5)
      }),
      threshold: 1,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
    });

    // Authentication monitoring alarms
    new cloudwatch.Alarm(this, 'AuthFailureAlarm', {
      alarmName: 'customer-support-auth-failures',
      alarmDescription: 'Alert on high authentication failure rate',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/Cognito',
        metricName: 'SignInSuccesses',
        dimensionsMap: {
          UserPool: userPool.userPoolId,
          UserPoolClient: userPoolClient.userPoolClientId
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5)
      }),
      threshold: 10,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD
    });

    new cloudwatch.Alarm(this, 'SuspiciousLoginAlarm', {
      alarmName: 'customer-support-suspicious-logins',
      alarmDescription: 'Alert on suspicious login patterns',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/Cognito',
        metricName: 'CompromisedCredentialsRisk',
        dimensionsMap: {
          UserPool: userPool.userPoolId
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5)
      }),
      threshold: 1,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
    });

    // CloudWatch Alarms are configured without SNS actions for basic monitoring

    // Memory configuration is now hardcoded in Lambda - no parameters needed

    new cdk.CfnOutput(this, 'MemoryManagerFunctionArn', {
      value: memoryManagerFunction.functionArn,
      description: 'ARN of the Memory Management Lambda function'
    });



    // Output agent deployment information - MIGRATED TO L1 CONSTRUCT
    // Preserving existing output names and adding L1 construct specific attributes
    new cdk.CfnOutput(this, 'SupervisorAgentRuntimeArn', {
      value: supervisorAgentRuntime.attrAgentRuntimeArn,
      description: 'ARN of the deployed Supervisor Agent Runtime (L1 construct)',
      exportName: 'CustomerSupportAssistantStack-SupervisorRuntimeArn'
    });

    new cdk.CfnOutput(this, 'SupervisorAgentRuntimeId', {
      value: supervisorAgentRuntime.attrAgentRuntimeId,
      description: 'ID of the deployed Supervisor Agent Runtime (L1 construct)'
    });

    // Additional L1 construct attributes for comprehensive monitoring and integration
    new cdk.CfnOutput(this, 'SupervisorAgentRuntimeName', {
      value: supervisorAgentRuntime.agentRuntimeName!,
      description: 'Name of the deployed Supervisor Agent Runtime'
    });

    // Note: CfnRuntime doesn't expose status attribute, only ARN and ID are available
    // This is expected behavior for L1 constructs which expose minimal attributes

    // Output container image URI for reference and debugging
    new cdk.CfnOutput(this, 'SupervisorAgentImageUri', {
      value: supervisorAgentImage.imageUri,
      description: 'Container image URI used by Supervisor Agent Runtime'
    });

    // Output resource dependency information for validation
    new cdk.CfnOutput(this, 'ResourceDependencyValidation', {
      value: `Memory:${memoryCustomResource.ref},Runtime:${supervisorAgentRuntime.attrAgentRuntimeId},Role:${agentExecutionRole.roleArn}`,
      description: 'Validation string showing proper resource dependency chain'
    });

    // Output summary of L1 construct migration status
    new cdk.CfnOutput(this, 'L1MigrationStatus', {
      value: 'COMPLETE - Agent Runtime migrated to native L1 construct, Memory still using custom resource',
      description: 'Status of L1 construct migration for monitoring and validation'
    });

    // Cognito User Pool outputs
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: userPool.userPoolId,
      description: 'Cognito User Pool ID for customer authentication'
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID for JWT token issuance',
      exportName: `${this.stackName}-UserPoolClientId`
    });

    new cdk.CfnOutput(this, 'UserPoolArn', {
      value: userPool.userPoolArn,
      description: 'Cognito User Pool ARN for IAM policies'
    });

    new cdk.CfnOutput(this, 'OIDCDiscoveryUrl', {
      value: `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`,
      description: 'OIDC Discovery URL for AgentCore Identity JWT validation',
      exportName: `${this.stackName}-OIDCDiscoveryUrl`
    });

    new cdk.CfnOutput(this, 'UserPoolDomainUrl', {
      value: `https://${userPoolDomain.domainName}.auth.${this.region}.amazoncognito.com`,
      description: 'Cognito Hosted UI domain URL for authentication'
    });

    new cdk.CfnOutput(this, 'CognitoLoginUrl', {
      value: `https://${userPoolDomain.domainName}.auth.${this.region}.amazoncognito.com/login?client_id=${userPoolClient.userPoolClientId}&response_type=code&scope=openid+email+profile&redirect_uri=https://localhost:3000/callback`,
      description: 'Complete Cognito login URL for testing authentication flow'
    });

    // SSM Parameter outputs
    new cdk.CfnOutput(this, 'WorkloadNameParameterName', {
      value: workloadNameParameter.parameterName,
      description: 'SSM Parameter name for agent workload identity'
    });

    new cdk.CfnOutput(this, 'PersonalizationRuntimeIdParameterName', {
      value: personalizationRuntimeIdParameterName,
      description: 'SSM Parameter name for personalization agent runtime ID',
      exportName: 'CustomerSupportAssistantStack-PersonalizationRuntimeIdParameterName'
    });

    new cdk.CfnOutput(this, 'OrderManagementRuntimeIdParameterName', {
      value: orderManagementRuntimeIdParameterName,
      description: 'SSM Parameter name for order management agent runtime ID',
      exportName: 'CustomerSupportAssistantStack-OrderManagementRuntimeIdParameterName'
    });

    new cdk.CfnOutput(this, 'ProductRecommendationRuntimeIdParameterName', {
      value: productRecommendationRuntimeIdParameterName,
      description: 'SSM Parameter name for product recommendation agent runtime ID',
      exportName: 'CustomerSupportAssistantStack-ProductRecommendationRuntimeIdParameterName'
    });

    new cdk.CfnOutput(this, 'TroubleshootingRuntimeIdParameterName', {
      value: troubleshootingRuntimeIdParameterName,
      description: 'SSM Parameter name for troubleshooting agent runtime ID',
      exportName: 'CustomerSupportAssistantStack-TroubleshootingRuntimeIdParameterName'
    });

    // Granular CDK-nag suppressions - starting with legitimate wildcards
    // Managed policy suppressions (Category 2: Standard AWS Patterns)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/MemoryManagerRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM4', 
        reason: 'Lambda functions require AWSLambdaBasicExecutionRole for CloudWatch logging',
        appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] 
      }]
    );

    // CDK custom resource wildcards (Category 1: CDK Deployment Infrastructure)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/MemoryManagerRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'CDK custom resource for memory management requires wildcard permissions because memory resources do not exist until created',
        appliesTo: ['Resource::*']
      }]
    );

    // CloudWatch logs wildcard for Lambda function (Category 4: Legitimate Technical Requirements)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/MemoryManagerRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'Lambda function requires wildcard CloudWatch logs permissions for log group and stream creation',
        appliesTo: ['Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/CustomerSupportAssistantStack-MemoryManagerFunction*']
      }]
    );

    // Cognito advanced security (Category 3: Demo/Development Constraints)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/CustomerSupportUserPool/Resource', 
      [{ 
        id: 'AwsSolutions-COG3', 
        reason: 'Demo application uses standard Cognito security. Advanced security mode not required for demonstration purposes'
      }]
    );

    // Legitimate wildcard permissions (Category 4: Legitimate Technical Requirements)
    // ECR GetAuthorizationToken - AWS service requirement
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/CustomerSupportAgentExecutionRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'ECR GetAuthorizationToken requires wildcard resource permissions as per AWS service design',
        appliesTo: ['Action::ecr:GetAuthorizationToken', 'Resource::*']
      }]
    );

    // X-Ray tracing - service requirement for distributed tracing
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/CustomerSupportAgentExecutionRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'X-Ray tracing requires wildcard resource permissions for distributed trace collection',
        appliesTo: ['Action::xray:PutTraceSegments', 'Action::xray:PutTelemetryRecords', 'Resource::*']
      }]
    );

    // Cognito SMS role wildcard (Category 4: Legitimate Technical Requirements)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/CustomerSupportUserPool/smsRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'Cognito SMS role requires wildcard permissions for SMS delivery across regions',
        appliesTo: ['Resource::*']
      }]
    );

    // CloudWatch logs wildcard (Category 4: Legitimate Technical Requirements)
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/CustomerSupportAssistantStack/CustomerSupportAgentExecutionRole/Resource', 
      [{ 
        id: 'AwsSolutions-IAM5', 
        reason: 'CloudWatch logs requires wildcard permissions because AgentCore creates log groups with unpredictable names',
        appliesTo: ['Action::logs:CreateLogGroup', 'Action::logs:CreateLogStream', 'Action::logs:PutLogEvents', 'Resource::arn:aws:logs:*:*:*']
      }]
    );
  }
}