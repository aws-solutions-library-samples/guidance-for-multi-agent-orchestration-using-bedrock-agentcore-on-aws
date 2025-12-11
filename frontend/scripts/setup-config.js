#!/usr/bin/env node

/**
 * Environment Configuration Setup Script
 * 
 * This script reads CloudFormation stack outputs from the CustomerSupportAssistantStack
 * and generates a .env.production file for the frontend build process.
 * 
 * Usage:
 *   node scripts/setup-config.js [--stack-name <name>] [--region <region>]
 * 
 * Options:
 *   --stack-name    CloudFormation stack name (default: CustomerSupportAssistantStack)
 *   --region        AWS region (default: us-east-1)
 *   --help          Show this help message
 */

import { CloudFormationClient, DescribeStacksCommand } from '@aws-sdk/client-cloudformation';
import { writeFileSync } from 'fs';
import { resolve, dirname, sep } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Parse command line arguments
function parseArgs() {
  const args = process.argv.slice(2);
  const config = {
    stackName: 'CustomerSupportAssistantStack',
    region: 'us-east-1',
    help: false
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--stack-name':
        config.stackName = args[++i];
        break;
      case '--region':
        config.region = args[++i];
        break;
      case '--help':
      case '-h':
        config.help = true;
        break;
      default:
        console.warn(`Unknown argument: ${args[i]}`);
    }
  }

  return config;
}

// Show help message
function showHelp() {
  console.log(`
Environment Configuration Setup Script

This script reads CloudFormation stack outputs and generates environment configuration.

Usage:
  node scripts/setup-config.js [options]

Options:
  --stack-name <name>    CloudFormation stack name (default: CustomerSupportAssistantStack)
  --region <region>      AWS region (default: us-east-1)
  --help, -h             Show this help message

Examples:
  # Use defaults
  npm run setup-config

  # Specify custom stack name
  npm run setup-config -- --stack-name MyCustomStack

  # Specify region
  npm run setup-config -- --region us-west-2

Required Stack Outputs:
  - SupervisorAgentRuntimeArn: ARN of the Supervisor agent runtime
  - UserPoolId: Cognito User Pool ID
  - UserPoolClientId: Cognito User Pool Client ID

The script will create a .env.production file with the following variables:
  - VITE_AWS_REGION
  - VITE_AGENTCORE_RUNTIME_ARN
  - VITE_USER_POOL_ID
  - VITE_USER_POOL_CLIENT_ID
`);
}

// Fetch CloudFormation stack outputs
async function getStackOutputs(stackName, region) {
  console.log(`Fetching outputs from stack: ${stackName} in region: ${region}`);
  
  const client = new CloudFormationClient({ region });
  
  try {
    const command = new DescribeStacksCommand({ StackName: stackName });
    const response = await client.send(command);
    
    if (!response.Stacks || response.Stacks.length === 0) {
      throw new Error(`Stack ${stackName} not found`);
    }
    
    const stack = response.Stacks[0];
    
    if (!stack.Outputs || stack.Outputs.length === 0) {
      throw new Error(`Stack ${stackName} has no outputs`);
    }
    
    // Convert outputs array to key-value object
    const outputs = {};
    for (const output of stack.Outputs) {
      if (output.OutputKey && output.OutputValue) {
        outputs[output.OutputKey] = output.OutputValue;
      }
    }
    
    console.log(`✓ Successfully retrieved ${Object.keys(outputs).length} outputs`);
    return outputs;
    
  } catch (error) {
    if (error.name === 'ValidationError') {
      throw new Error(`Stack ${stackName} does not exist in region ${region}`);
    }
    throw error;
  }
}

// Validate required outputs
function validateOutputs(outputs) {
  const required = [
    'SupervisorAgentRuntimeArn',
    'UserPoolId',
    'UserPoolClientId'
  ];
  
  const missing = required.filter(key => !outputs[key]);
  
  if (missing.length > 0) {
    throw new Error(
      `Missing required stack outputs: ${missing.join(', ')}\n` +
      `Available outputs: ${Object.keys(outputs).join(', ')}`
    );
  }
  
  console.log('✓ All required outputs found');
}

// Generate .env file content
function generateEnvContent(outputs, region) {
  const timestamp = new Date().toISOString();
  
  return `# Auto-generated environment configuration
# Generated at: ${timestamp}
# Source: CloudFormation stack outputs

# AWS Region where the Cognito User Pool is deployed
VITE_AWS_REGION=${region}

# AgentCore Runtime ARN from CustomerSupportAssistantStack output
# Frontend calls this directly with JWT authentication
VITE_AGENTCORE_RUNTIME_ARN=${outputs.SupervisorAgentRuntimeArn}

# User Pool ID from CustomerSupportAssistantStack output
VITE_USER_POOL_ID=${outputs.UserPoolId}

# User Pool Client ID from CustomerSupportAssistantStack output
VITE_USER_POOL_CLIENT_ID=${outputs.UserPoolClientId}
`;
}

// Write .env file
function writeEnvFile(content) {
  const outputPath = resolve(__dirname, '..', '.env.production');
  
  try {
    writeFileSync(outputPath, content, 'utf8');
    console.log(`✓ Configuration written to: ${outputPath}`);
  } catch (error) {
    throw new Error(`Failed to write file ${outputPath}: ${error.message}`);
  }
}

// Main execution
async function main() {
  const config = parseArgs();
  
  if (config.help) {
    showHelp();
    process.exit(0);
  }
  
  console.log('\n🔧 Setting up environment configuration...\n');
  
  try {
    // Fetch stack outputs
    const outputs = await getStackOutputs(config.stackName, config.region);
    
    // Validate required outputs
    validateOutputs(outputs);
    
    // Generate .env content
    const envContent = generateEnvContent(outputs, config.region);
    
    // Write to file
    writeEnvFile(envContent);
    
    console.log('\n✅ Environment configuration setup complete!\n');
    console.log('Next steps:');
    console.log('  1. Review the generated configuration file');
    console.log('  2. Run "npm run build" to build the frontend');
    console.log('  3. Run "npm run deploy" to deploy to AWS\n');
    
    process.exit(0);
    
  } catch (error) {
    console.error('\n❌ Error setting up configuration:\n');
    console.error(error.message);
    console.error('\nTroubleshooting:');
    console.error('  - Ensure AWS credentials are configured (aws configure)');
    console.error('  - Verify the CloudFormation stack exists and is deployed');
    console.error('  - Check that you have permissions to describe CloudFormation stacks');
    console.error('  - Use --help for usage information\n');
    process.exit(1);
  }
}

main();
