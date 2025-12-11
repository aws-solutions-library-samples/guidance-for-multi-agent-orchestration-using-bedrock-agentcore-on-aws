import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';
import * as path from 'path';

export interface KnowledgeBaseStackProps extends cdk.StackProps {
  environment: string;
}

export class KnowledgeBaseStack extends cdk.Stack {
  public readonly personalizationKnowledgeBase: bedrock.CfnKnowledgeBase;
  public readonly troubleshootingKnowledgeBase: bedrock.CfnKnowledgeBase;
  public readonly personalizationDataSource: bedrock.CfnDataSource;
  public readonly troubleshootingDataSource: bedrock.CfnDataSource;
  public readonly personalizationDataBucket: s3.Bucket;
  public readonly troubleshootingDataBucket: s3.Bucket;
  public readonly opensearchCollection: opensearchserverless.CfnCollection;

  constructor(scope: Construct, id: string, props: KnowledgeBaseStackProps) {
    super(scope, id, props);

    const { environment } = props;

    // KMS Key for encryption
    const kmsKey = new kms.Key(this, 'KnowledgeBaseKey', {
      description: 'KMS key for Knowledge Base encryption',
      enableKeyRotation: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // S3 Access Logs Bucket (for server access logging)
    const accessLogsBucket = new s3.Bucket(this, 'AccessLogsBucket', {
      bucketName: `agentcore-access-logs-${environment}-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: kmsKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
    });

    // S3 Buckets for data
    // Includes region in name to prevent collisions across multi-region deployments
    this.personalizationDataBucket = new s3.Bucket(this, 'PersonalizationDataBucket', {
      bucketName: `agentcore-personalization-data-${environment}-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: kmsKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'personalization-data-access-logs/',
    });

    this.troubleshootingDataBucket = new s3.Bucket(this, 'TroubleshootingDataBucket', {
      bucketName: `agentcore-troubleshooting-data-${environment}-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: kmsKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'troubleshooting-data-access-logs/',
    });

    // Collection name for OpenSearch Serverless (must be unique across all regions in account)
    const collectionName = `bedrock-kb-${environment}-${cdk.Aws.REGION}`;

    // Bedrock service role
    // Simplified OpenSearch Serverless setup
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'EncryptionPolicy', {
      name: `${collectionName}-enc`,
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [{ ResourceType: 'collection', Resource: [`collection/${collectionName}`] }],
        AWSOwnedKey: true,
      }),
    });

    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'NetworkPolicy', {
      name: `${collectionName}-net`,
      type: 'network',
      policy: JSON.stringify([{
        Rules: [{ ResourceType: 'collection', Resource: [`collection/${collectionName}`] }],
        AllowFromPublic: true,
      }]),
    });

    this.opensearchCollection = new opensearchserverless.CfnCollection(this, 'OpenSearchCollection', {
      name: collectionName,
      type: 'VECTORSEARCH',
      standbyReplicas: 'DISABLED',
    });

    // Create Bedrock service role (after OpenSearch collection is defined)
    const bedrockServiceRole = new iam.Role(this, 'BedrockServiceRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Service role for Bedrock Knowledge Base',
      inlinePolicies: {
        BedrockKnowledgeBasePolicy: new iam.PolicyDocument({
          statements: [
            // OpenSearch Serverless permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['aoss:APIAccessAll'],
              resources: [this.opensearchCollection.attrArn],
            }),
            // S3 permissions for data sources
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['s3:GetObject', 's3:ListBucket', 's3:GetBucketLocation'],
              resources: [
                this.personalizationDataBucket.bucketArn,
                this.troubleshootingDataBucket.bucketArn,
              ],
            }),
            // Bedrock model invocation
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['bedrock:InvokeModel'],
              resources: [
                `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
                `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0`,
              ],
            }),
            // KMS permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['kms:Decrypt', 'kms:GenerateDataKey'],
              resources: [kmsKey.keyArn],
            }),
          ],
        }),
      },
    });

    // Grant S3 read permissions using CDK's built-in methods
    this.personalizationDataBucket.grantRead(bedrockServiceRole);
    this.troubleshootingDataBucket.grantRead(bedrockServiceRole);

    // Suppress legitimate S3 wildcards required for bucket/object access
    NagSuppressions.addResourceSuppressions(bedrockServiceRole, [
      { 
        id: 'AwsSolutions-IAM5', 
        reason: 'S3 read access requires wildcard permissions for bucket operations and object access patterns',
        appliesTo: [
          'Action::s3:GetBucket*',
          'Action::s3:GetObject*', 
          'Action::s3:List*',
          'Resource::<PersonalizationDataBucket804E7780.Arn>/*',
          'Resource::<TroubleshootingDataBucketD4405A62.Arn>/*'
        ]
      }
    ], true);

    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'DataAccessPolicy', {
      name: `${collectionName}-access`,
      type: 'data',
      policy: JSON.stringify([{
        Rules: [
          {
            Resource: [`collection/${collectionName}`],
            Permission: ['aoss:CreateCollectionItems', 'aoss:UpdateCollectionItems', 'aoss:DescribeCollectionItems'],
            ResourceType: 'collection',
          },
          {
            Resource: [`index/${collectionName}/*`],
            Permission: ['aoss:CreateIndex', 'aoss:UpdateIndex', 'aoss:DescribeIndex', 'aoss:DeleteIndex', 'aoss:ReadDocument', 'aoss:WriteDocument'],
            ResourceType: 'index',
          },
        ],
        Principal: [
          bedrockServiceRole.roleArn,
          `arn:aws:iam::${this.account}:role/cdk-hnb659fds-cfn-exec-role-${this.account}-${this.region}`, // CDK execution role (exact ARN)
        ],
      }]),
    });

    // Dependencies
    networkPolicy.node.addDependency(encryptionPolicy);
    this.opensearchCollection.node.addDependency(networkPolicy);
    dataAccessPolicy.node.addDependency(this.opensearchCollection);

    // Add wait condition to ensure collection is active before creating indexes
    const waitCondition = new cdk.custom_resources.AwsCustomResource(this, 'WaitForCollection', {
      onCreate: {
        service: 'OpenSearchServerless',
        action: 'batchGetCollection',
        parameters: {
          names: [collectionName]
        },
        physicalResourceId: cdk.custom_resources.PhysicalResourceId.of('WaitForCollection'),
      },
      policy: cdk.custom_resources.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cdk.custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
      timeout: cdk.Duration.minutes(5),
    });

    waitCondition.node.addDependency(this.opensearchCollection);
    waitCondition.node.addDependency(dataAccessPolicy);

    // Create OpenSearch indexes (required before Knowledge Bases)
    const personalizationIndex = new opensearchserverless.CfnIndex(this, 'PersonalizationIndex', {
      collectionEndpoint: this.opensearchCollection.attrCollectionEndpoint,
      indexName: 'personalization-index',
      mappings: {
        properties: {
          'bedrock-knowledge-base-default-vector': {
            type: 'knn_vector',
            dimension: 1024,
            method: {
              engine: 'faiss',
              name: 'hnsw',
              parameters: {
                efConstruction: 512,
                m: 16,
              },
              spaceType: 'l2',
            },
          },
          'AMAZON_BEDROCK_METADATA': { type: 'text', index: true },
          'AMAZON_BEDROCK_TEXT_CHUNK': { type: 'text', index: true },
        },
      },
      settings: {
        index: {
          knn: true,
          knnAlgoParamEfSearch: 512,
        },
      },
    });

    const troubleshootingIndex = new opensearchserverless.CfnIndex(this, 'TroubleshootingIndex', {
      collectionEndpoint: this.opensearchCollection.attrCollectionEndpoint,
      indexName: 'troubleshooting-index',
      mappings: {
        properties: {
          'bedrock-knowledge-base-default-vector': {
            type: 'knn_vector',
            dimension: 1024,
            method: {
              engine: 'faiss',
              name: 'hnsw',
              parameters: {
                efConstruction: 512,
                m: 16,
              },
              spaceType: 'l2',
            },
          },
          'AMAZON_BEDROCK_METADATA': { type: 'text', index: true },
          'AMAZON_BEDROCK_TEXT_CHUNK': { type: 'text', index: true },
        },
      },
      settings: {
        index: {
          knn: true,
          knnAlgoParamEfSearch: 512,
        },
      },
    });

    // Index dependencies
    personalizationIndex.node.addDependency(dataAccessPolicy);
    personalizationIndex.node.addDependency(this.opensearchCollection);
    personalizationIndex.node.addDependency(waitCondition);
    troubleshootingIndex.node.addDependency(dataAccessPolicy);
    troubleshootingIndex.node.addDependency(this.opensearchCollection);
    troubleshootingIndex.node.addDependency(waitCondition);

    // Wait for indexes to be queryable by Bedrock
    const waitForIndexes = new cdk.custom_resources.AwsCustomResource(this, 'WaitForIndexes', {
      onCreate: {
        service: 'OpenSearchServerless',
        action: 'batchGetCollection',
        parameters: {
          names: [collectionName]
        },
        physicalResourceId: cdk.custom_resources.PhysicalResourceId.of('WaitForIndexes'),
      },
      policy: cdk.custom_resources.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cdk.custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
      timeout: cdk.Duration.minutes(5),
    });

    waitForIndexes.node.addDependency(personalizationIndex);
    waitForIndexes.node.addDependency(troubleshootingIndex);

    // Knowledge Bases
    this.personalizationKnowledgeBase = new bedrock.CfnKnowledgeBase(this, 'PersonalizationKnowledgeBase', {
      name: `PersonalizationKB-${environment}`,
      description: 'Knowledge base for customer browsing history and personalization data',
      roleArn: bedrockServiceRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: this.opensearchCollection.attrArn,
          vectorIndexName: 'personalization-index',
          fieldMapping: {
            vectorField: 'bedrock-knowledge-base-default-vector',
            textField: 'AMAZON_BEDROCK_TEXT_CHUNK',
            metadataField: 'AMAZON_BEDROCK_METADATA',
          },
        },
      },
    });

    this.troubleshootingKnowledgeBase = new bedrock.CfnKnowledgeBase(this, 'TroubleshootingKnowledgeBase', {
      name: `TroubleshootingKB-${environment}`,
      description: 'Knowledge base for FAQs and troubleshooting guides',
      roleArn: bedrockServiceRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: this.opensearchCollection.attrArn,
          vectorIndexName: 'troubleshooting-index',
          fieldMapping: {
            vectorField: 'bedrock-knowledge-base-default-vector',
            textField: 'AMAZON_BEDROCK_TEXT_CHUNK',
            metadataField: 'AMAZON_BEDROCK_METADATA',
          },
        },
      },
    });

    // Data Sources
    this.personalizationDataSource = new bedrock.CfnDataSource(this, 'PersonalizationDataSource', {
      knowledgeBaseId: this.personalizationKnowledgeBase.attrKnowledgeBaseId,
      name: `PersonalizationS3DataSource-${environment}`,
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: this.personalizationDataBucket.bucketArn,
          inclusionPrefixes: ['browsing-history/'],
        },
      },
    });

    this.troubleshootingDataSource = new bedrock.CfnDataSource(this, 'TroubleshootingDataSource', {
      knowledgeBaseId: this.troubleshootingKnowledgeBase.attrKnowledgeBaseId,
      name: `TroubleshootingS3DataSource-${environment}`,
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: this.troubleshootingDataBucket.bucketArn,
          inclusionPrefixes: ['faqs/'],
        },
      },
    });

    // Dependencies for Knowledge Bases
    this.personalizationKnowledgeBase.node.addDependency(waitForIndexes);
    this.troubleshootingKnowledgeBase.node.addDependency(waitForIndexes);

    // Deploy sample data to S3 buckets
    const personalizationDataPath = path.join(__dirname, '../../knowledge-base-data/browsing-history');
    const troubleshootingDataPath = path.join(__dirname, '../../knowledge-base-data/faqs');

    new s3deploy.BucketDeployment(this, 'PersonalizationDataDeployment', {
      sources: [s3deploy.Source.asset(personalizationDataPath)],
      destinationBucket: this.personalizationDataBucket,
      destinationKeyPrefix: 'browsing-history/',
    });

    new s3deploy.BucketDeployment(this, 'TroubleshootingDataDeployment', {
      sources: [s3deploy.Source.asset(troubleshootingDataPath)],
      destinationBucket: this.troubleshootingDataBucket,
      destinationKeyPrefix: 'faqs/',
    });

    // Trigger ingestion jobs after data deployment
    const personalizationIngestion = new cdk.custom_resources.AwsCustomResource(this, 'PersonalizationIngestion', {
      onCreate: {
        service: 'BedrockAgent',
        action: 'startIngestionJob',
        parameters: {
          knowledgeBaseId: this.personalizationKnowledgeBase.attrKnowledgeBaseId,
          dataSourceId: this.personalizationDataSource.attrDataSourceId,
        },
        physicalResourceId: cdk.custom_resources.PhysicalResourceId.fromResponse('ingestionJob.ingestionJobId'),
      },
      policy: cdk.custom_resources.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cdk.custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
    });

    const troubleshootingIngestion = new cdk.custom_resources.AwsCustomResource(this, 'TroubleshootingIngestion', {
      onCreate: {
        service: 'BedrockAgent',
        action: 'startIngestionJob',
        parameters: {
          knowledgeBaseId: this.troubleshootingKnowledgeBase.attrKnowledgeBaseId,
          dataSourceId: this.troubleshootingDataSource.attrDataSourceId,
        },
        physicalResourceId: cdk.custom_resources.PhysicalResourceId.fromResponse('ingestionJob.ingestionJobId'),
      },
      policy: cdk.custom_resources.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cdk.custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
    });

    // Ensure ingestion happens after data deployment
    personalizationIngestion.node.addDependency(this.personalizationDataSource);
    troubleshootingIngestion.node.addDependency(this.troubleshootingDataSource);

    // Outputs
    new cdk.CfnOutput(this, 'PersonalizationKnowledgeBaseId', {
      value: this.personalizationKnowledgeBase.attrKnowledgeBaseId,
      exportName: `${this.stackName}-PersonalizationKnowledgeBaseId`,
    });

    new cdk.CfnOutput(this, 'TroubleshootingKnowledgeBaseId', {
      value: this.troubleshootingKnowledgeBase.attrKnowledgeBaseId,
      exportName: `${this.stackName}-TroubleshootingKnowledgeBaseId`,
    });

    new cdk.CfnOutput(this, 'PersonalizationDataBucketName', {
      value: this.personalizationDataBucket.bucketName,
      exportName: `${this.stackName}-PersonalizationDataBucketName`,
    });

    new cdk.CfnOutput(this, 'TroubleshootingDataBucketName', {
      value: this.troubleshootingDataBucket.bucketName,
      exportName: `${this.stackName}-TroubleshootingDataBucketName`,
    });

    // CDK-nag suppressions for CDK-generated deployment resources only
    // These are temporary deployment helpers, not runtime application resources
    NagSuppressions.addResourceSuppressionsByPath(this, [
      '/KnowledgeBaseStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole',
      '/KnowledgeBaseStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole/DefaultPolicy',
      '/KnowledgeBaseStack/AWS679f53fac002430cb0da5b7982bd2287/ServiceRole',
      '/KnowledgeBaseStack/WaitForCollection/CustomResourcePolicy',
      '/KnowledgeBaseStack/WaitForIndexes/CustomResourcePolicy', 
      '/KnowledgeBaseStack/PersonalizationIngestion/CustomResourcePolicy',
      '/KnowledgeBaseStack/TroubleshootingIngestion/CustomResourcePolicy'
    ], [
    ]);

    // Granular CDK-nag suppressions for specific CDK-generated violations
    // BucketDeployment managed policy requirement
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole', 
      [{ id: 'AwsSolutions-IAM4', reason: 'CDK BucketDeployment requires AWSLambdaBasicExecutionRole for deployment operations', appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] }]
    );

    // BucketDeployment wildcard permissions for S3 and KMS operations
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole/DefaultPolicy', 
      [{ id: 'AwsSolutions-IAM5', reason: 'CDK BucketDeployment requires S3 and KMS wildcards for file deployment operations', appliesTo: [
        'Action::s3:GetBucket*', 'Action::s3:GetObject*', 'Action::s3:List*', 'Action::s3:Abort*', 'Action::s3:DeleteObject*',
        'Action::kms:GenerateDataKey*', 'Action::kms:ReEncrypt*',
        'Resource::arn:<AWS::Partition>:s3:::cdk-hnb659fds-assets-<AWS::AccountId>-<AWS::Region>/*',
        'Resource::<PersonalizationDataBucket804E7780.Arn>/*', 'Resource::<TroubleshootingDataBucketD4405A62.Arn>/*'
      ]}]
    );

    // CDK Lambda helper managed policy requirement  
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/AWS679f53fac002430cb0da5b7982bd2287/ServiceRole', 
      [{ id: 'AwsSolutions-IAM4', reason: 'CDK-generated Lambda requires AWSLambdaBasicExecutionRole for CloudWatch logging', appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'] }]
    );

    // Custom resource policies for OpenSearch and Bedrock operations
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/WaitForCollection/CustomResourcePolicy', 
      [{ id: 'AwsSolutions-IAM5', reason: 'OpenSearch collection operations require wildcard resource permissions', appliesTo: ['Resource::*'] }]
    );

    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/WaitForIndexes/CustomResourcePolicy', 
      [{ id: 'AwsSolutions-IAM5', reason: 'OpenSearch index operations require wildcard resource permissions', appliesTo: ['Resource::*'] }]
    );

    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/PersonalizationIngestion/CustomResourcePolicy', 
      [{ id: 'AwsSolutions-IAM5', reason: 'Bedrock knowledge base ingestion requires wildcard resource permissions', appliesTo: ['Resource::*'] }]
    );

    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/TroubleshootingIngestion/CustomResourcePolicy', 
      [{ id: 'AwsSolutions-IAM5', reason: 'Bedrock knowledge base ingestion requires wildcard resource permissions', appliesTo: ['Resource::*'] }]
    );

    // Suppress Lambda runtime warnings for CDK-managed functions
    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/AWS679f53fac002430cb0da5b7982bd2287/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'CDK-managed Lambda function runtime is controlled by CDK version, not user code' }]
    );

    NagSuppressions.addResourceSuppressionsByPath(this, 
      '/KnowledgeBaseStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/Resource', 
      [{ id: 'AwsSolutions-L1', reason: 'CDK BucketDeployment Lambda runtime is controlled by CDK version, not user code' }]
    );
  }
}
