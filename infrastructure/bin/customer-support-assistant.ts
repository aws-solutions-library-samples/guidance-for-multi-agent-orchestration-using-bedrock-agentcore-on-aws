#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CustomerSupportAssistantStack } from '../lib/customer-support-assistant-stack';
import { KnowledgeBaseStack } from '../lib/knowledge-base-stack';
import { PersonalizationAgentStack } from '../lib/personalization-agent-stack';
import { OrderManagementAgentStack } from '../lib/order-management-agent-stack';
import { ProductRecommendationAgentStack } from '../lib/product-recommendation-agent-stack';
import { TroubleshootingAgentStack } from '../lib/troubleshooting-agent-stack';
import { FrontendStack } from '../lib/frontend-stack';
import { AwsSolutionsChecks } from 'cdk-nag';
import { Aspects } from 'aws-cdk-lib';

const app = new cdk.App();

// Add CDK-nag AwsSolutions Pack with verbose logging
Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

// Get backend region for frontend naming (prevents collisions when deploying to multiple regions)
const backendRegion = process.env.AWS_REGION || process.env.CDK_DEFAULT_REGION || 'us-east-1';

// Deploy Knowledge Base stack first (other stacks will import its outputs)
const knowledgeBaseStack = new KnowledgeBaseStack(app, 'KnowledgeBaseStack', {
  environment: 'dev',
});

// Main AgentCore stack
const mainStack = new CustomerSupportAssistantStack(app, 'CustomerSupportAssistantStack', {
  description: 'Guidance for Multi-Agent Orchestration using Amazon Bedrock AgentCore on AWS (SO9035)',
});


// Personalization Agent stack (uses shared resources from main stack)
const personalizationStack = new PersonalizationAgentStack(app, 'PersonalizationAgentStack', {
  orchestratorStackName: 'CustomerSupportAssistantStack',
  memoryId: cdk.Fn.importValue('CustomerSupportAssistantStack-MemoryId'),
  executionRoleArn: cdk.Fn.importValue('CustomerSupportAssistantStack-AgentExecutionRoleArn'),
  cognitoDiscoveryUrl: cdk.Fn.importValue('CustomerSupportAssistantStack-OIDCDiscoveryUrl'),
  cognitoClientId: cdk.Fn.importValue('CustomerSupportAssistantStack-UserPoolClientId'),
  knowledgeBaseId: knowledgeBaseStack.personalizationKnowledgeBase.attrKnowledgeBaseId,
  runtimeIdParameterName: mainStack.personalizationRuntimeIdParameterName,
});

// Order Management Agent stack (uses shared resources from main stack)
const orderManagementStack = new OrderManagementAgentStack(app, 'OrderManagementAgentStack', {
  orchestratorStackName: 'CustomerSupportAssistantStack',
  executionRoleArn: cdk.Fn.importValue('CustomerSupportAssistantStack-AgentExecutionRoleArn'),
  cognitoDiscoveryUrl: cdk.Fn.importValue('CustomerSupportAssistantStack-OIDCDiscoveryUrl'),
  cognitoClientId: cdk.Fn.importValue('CustomerSupportAssistantStack-UserPoolClientId'),
  runtimeIdParameterName: mainStack.orderManagementRuntimeIdParameterName,
});

// Product Recommendation Agent stack (uses shared resources from main stack)
const productRecommendationStack = new ProductRecommendationAgentStack(app, 'ProductRecommendationAgentStack', {
  orchestratorStackName: mainStack.stackName,
  memoryId: cdk.Fn.importValue('CustomerSupportAssistantStack-MemoryId'),
  executionRoleArn: cdk.Fn.importValue('CustomerSupportAssistantStack-AgentExecutionRoleArn'),
  cognitoDiscoveryUrl: cdk.Fn.importValue('CustomerSupportAssistantStack-OIDCDiscoveryUrl'),
  cognitoClientId: cdk.Fn.importValue('CustomerSupportAssistantStack-UserPoolClientId'),
  runtimeIdParameterName: mainStack.productRecommendationRuntimeIdParameterName,
});

// Troubleshooting Agent stack (uses shared resources from main stack)
const troubleshootingStack = new TroubleshootingAgentStack(app, 'TroubleshootingAgentStack', {
  orchestratorStackName: 'CustomerSupportAssistantStack',
  memoryId: cdk.Fn.importValue('CustomerSupportAssistantStack-MemoryId'),
  executionRoleArn: cdk.Fn.importValue('CustomerSupportAssistantStack-AgentExecutionRoleArn'),
  cognitoDiscoveryUrl: cdk.Fn.importValue('CustomerSupportAssistantStack-OIDCDiscoveryUrl'),
  cognitoClientId: cdk.Fn.importValue('CustomerSupportAssistantStack-UserPoolClientId'),
  knowledgeBaseId: knowledgeBaseStack.troubleshootingKnowledgeBase.attrKnowledgeBaseId,
  runtimeIdParameterName: mainStack.troubleshootingRuntimeIdParameterName,
});

// Ensure agent stacks deploy after main stack and knowledge base stack
personalizationStack.addDependency(mainStack);
personalizationStack.addDependency(knowledgeBaseStack);
orderManagementStack.addDependency(mainStack);
productRecommendationStack.addDependency(mainStack);
troubleshootingStack.addDependency(mainStack);
troubleshootingStack.addDependency(knowledgeBaseStack);

// Frontend stack - MUST deploy to us-east-1 due to AWS CloudFront WAF requirement
// AWS requires WAFv2 WebACL with scope:CLOUDFRONT to be created in us-east-1
// See: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-wafv2-webacl.html
// Stack is named by backend region to prevent collisions across multi-region deployments
const frontendStack = new FrontendStack(app, `FrontendStack-${backendRegion}`, {
  env: { region: 'us-east-1' },  // CloudFront WAF requirement - do not change
  backendRegion: backendRegion,
});
