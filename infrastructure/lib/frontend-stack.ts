import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as cloudfront_origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

export interface FrontendStackProps extends cdk.StackProps {
  backendRegion: string;
}

export class FrontendStack extends cdk.Stack {
  public readonly distribution: cloudfront.Distribution;
  public readonly websiteBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    const backendRegion = props.backendRegion;

    // S3 Access Logs Bucket for website bucket
    const accessLogsBucket = new s3.Bucket(this, 'AccessLogsBucket', {
      bucketName: `customer-support-frontend-logs-${cdk.Aws.ACCOUNT_ID}-${backendRegion}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED, // Enable ACLs for CloudFront logging
    });

    // S3 bucket for static website hosting
    // Note: This stack always deploys to us-east-1 (CloudFront WAF requirement),
    // but bucket name includes backend region to prevent collisions when deploying
    // to multiple backend regions (e.g., us-east-1 backend and us-west-2 backend
    // both create frontend stacks in us-east-1 with different bucket names)
    this.websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName: `customer-support-frontend-${cdk.Aws.ACCOUNT_ID}-${backendRegion}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'website-access-logs/',
    });

    // Origin Access Control for S3
    const oac = new cloudfront.S3OriginAccessControl(this, 'MyOAC', {
      signing: cloudfront.Signing.SIGV4_NO_OVERRIDE
    });

    // WAF Web ACL for CloudFront
    const webAcl = new wafv2.CfnWebACL(this, 'WebAcl', {
      scope: 'CLOUDFRONT',
      defaultAction: { allow: {} },
      rules: [
        {
          name: 'AWSManagedRulesCommonRuleSet',
          priority: 1,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesCommonRuleSet',
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'CommonRuleSetMetric',
          },
        },
      ],
      visibilityConfig: {
        sampledRequestsEnabled: true,
        cloudWatchMetricsEnabled: true,
        metricName: 'WebAclMetric',
      },
    });

    // CloudFront distribution
    // CloudFront Response Headers Policy for security
    const responseHeadersPolicy = new cloudfront.ResponseHeadersPolicy(this, 'SecurityHeaders', {
      securityHeadersBehavior: {
        contentTypeOptions: { override: true },
        frameOptions: { frameOption: cloudfront.HeadersFrameOption.DENY, override: true },
        referrerPolicy: { referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN, override: true },
        strictTransportSecurity: { accessControlMaxAge: cdk.Duration.seconds(31536000), includeSubdomains: true, override: true },
      },
    });

    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: cloudfront_origins.S3BucketOrigin.withOriginAccessControl(this.websiteBucket, {
          originAccessControl: oac
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        compress: true,
        responseHeadersPolicy: responseHeadersPolicy,
      },
      defaultRootObject: 'index.html',
      // Note: Error responses removed to prevent serving index.html for missing assets
      // SPA routing is handled by the application itself
      webAclId: webAcl.attrArn,
      // CloudFront access logging
      enableLogging: true,
      logBucket: accessLogsBucket,
      logFilePrefix: 'cloudfront-access-logs/',
      // Minimum TLS version
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
    });

    // Note: Frontend deployment is handled by the deployment script (deploy-complete-system.sh)
    // This ensures environment variables are properly configured before building.
    // The script:
    // 1. Generates .env.production from CloudFormation outputs
    // 2. Builds the frontend with proper environment variables
    // 3. Uploads to S3 using AWS CLI
    // 4. Invalidates CloudFront cache
    //
    // Do NOT use BucketDeployment here as it would try to deploy during CDK synthesis
    // before environment variables are available.

    // Outputs
    new cdk.CfnOutput(this, 'WebsiteURL', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: 'Frontend URL',
      exportName: `${this.stackName}-WebsiteURL`,
    });

    new cdk.CfnOutput(this, 'DistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront Distribution ID',
      exportName: `${this.stackName}-DistributionId`,
    });

    new cdk.CfnOutput(this, 'BucketName', {
      value: this.websiteBucket.bucketName,
      description: 'S3 Bucket Name',
      exportName: `${this.stackName}-BucketName`,
    });

    // Note: These outputs are redundant - values are already exported by CustomerSupportAssistantStack
    // new cdk.CfnOutput(this, 'SupervisorRuntimeArn', {
    //   value: supervisorRuntimeArn,
    //   description: 'Supervisor Agent Runtime ARN (imported from CustomerSupportAssistantStack)',
    // });

    // new cdk.CfnOutput(this, 'UserPoolClientId', {
    //   value: userPoolClientId,
    //   description: 'Cognito User Pool Client ID (imported from CustomerSupportAssistantStack)',
    // });

    new cdk.CfnOutput(this, 'Region', {
      value: this.region,
      description: 'AWS Region',
    });

    // Note: UserPoolId is available from CustomerSupportAssistantStack outputs
    // but is not exported. Retrieve it directly from that stack's outputs when needed.

    // Suppress CFR4 for demo application - custom SSL certificate not required
    NagSuppressions.addResourceSuppressions(this.distribution, [
      { 
        id: 'AwsSolutions-CFR4', 
        reason: 'Demo application uses default CloudFront certificate. Custom SSL certificate with domain validation not required for demonstration purposes.' 
      }
    ]);
  }
}
