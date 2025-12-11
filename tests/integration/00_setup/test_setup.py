#!/usr/bin/env python3
"""
Test 00: Setup - Extract stack outputs and create test user.

This script:
1. Queries CloudFormation stacks for all deployed resources
2. Extracts Runtime ARNs, Gateway IDs, Cognito details, Memory ID, KB ID
3. Generates test_config.json with all extracted values
4. Creates a test user in Cognito for authentication testing

Requirements: 1.7, 4.4
"""

import json
import os
import sys
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.aws_operations import extract_stack_outputs
from utils.authentication import create_test_user
from utils.config import save_config, validate_config
from utils.errors import TestError


def collect_stack_outputs(region: str = 'us-east-1') -> Dict[str, Any]:
    """
    Collect outputs from all CloudFormation stacks.
    
    Args:
        region: AWS region to query stacks in
        
    Returns:
        Dictionary containing all extracted configuration values
    """
    print("Extracting stack outputs...")
    
    config = {'aws_region': region}
    
    # Define stack-to-output mappings
    stack_mappings = {
        'KnowledgeBaseStack': {
            'PersonalizationKnowledgeBaseId': 'kb_id',
            'TroubleshootingKnowledgeBaseId': 'troubleshooting_kb_id'
        },
        'CustomerSupportAssistantStack': {
            'SupervisorAgentRuntimeArn': 'supervisor_runtime_arn',
            'UserPoolId': 'cognito_user_pool_id',
            'UserPoolClientId': 'cognito_client_id',
            'MemoryId': 'memory_id'
        },
        'OrderManagementAgentStack': {
            'OrderManagementAgentRuntimeArn': 'order_mgmt_runtime_arn',
            'GatewayId': 'order_mgmt_gateway_id'
        },
        'PersonalizationAgentStack': {
            'PersonalizationAgentRuntimeArn': 'personalization_runtime_arn',
            'GatewayId': 'personalization_gateway_id'
        },
        'ProductRecommendationAgentStack': {
            'ProductRecommendationAgentRuntimeArn': 'product_recommendation_runtime_arn',
            'SponsoredGatewayId': 'product_recommendation_sponsored_gateway_id',
            'OrganicGatewayId': 'product_recommendation_organic_gateway_id'
        },
        'TroubleshootingAgentStack': {
            'TroubleshootingAgentRuntimeArn': 'troubleshooting_runtime_arn',
            'GatewayId': 'troubleshooting_gateway_id'
        }
    }
    
    for stack_name, mappings in stack_mappings.items():
        try:
            outputs = extract_stack_outputs(stack_name, region)
            for output_key, config_key in mappings.items():
                if output_key in outputs:
                    config[config_key] = outputs[output_key]
                    print(f"  ✓ {config_key}: {outputs[output_key][:50]}...")
        except TestError as e:
            print(f"  ⚠ Warning: Could not extract outputs from {stack_name}: {e.message}")
    
    return config


def setup_test_user(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use existing test user from scripts/test_users_config-{region}.json.
    
    Args:
        config: Configuration dictionary to add test user to
        
    Returns:
        Updated configuration dictionary with test_user section
    """
    if 'cognito_user_pool_id' not in config:
        print("⚠ Warning: Cognito User Pool ID not found, skipping test user setup")
        return config
    
    # Try to load existing test users from scripts/test_users_config-{region}.json
    import json
    import os
    from pathlib import Path
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    test_users_config_path = Path(__file__).parent.parent.parent.parent / 'scripts' / f'test_users_config-{region}.json'
    
    if test_users_config_path.exists():
        print(f"\nUsing existing test users from scripts/test_users_config-{region}.json...")
        try:
            with open(test_users_config_path, 'r') as f:
                test_users_config = json.load(f)
            
            # Use first user from the users array
            if 'users' in test_users_config and len(test_users_config['users']) > 0:
                first_user = test_users_config['users'][0]
                test_user = {
                    'username': first_user['email'],
                    'password': first_user['password'],
                    'customer_id': first_user['customer_id']
                }
                config['test_user'] = test_user
                print(f"✓ Using test user: {test_user['username']} (customer_id: {test_user['customer_id']})")
                return config
        except Exception as e:
            print(f"⚠ Error: Could not load test users config: {e}")
            print("Please run the deployment script to generate test users or update the test user configuration file.")
            raise TestError(f"Test users configuration not found: {e}")

    return config


def print_config_summary(config: Dict[str, Any]) -> None:
    """
    Print a summary of the extracted configuration.
    
    Args:
        config: Configuration dictionary to summarize
    """
    print("\n" + "=" * 60)
    print("Configuration Summary")
    print("=" * 60)
    print(f"Region: {config.get('aws_region', 'N/A')}")
    print(f"\nRuntimes:")
    print(f"  • Supervisor: {config.get('supervisor_runtime_arn', 'N/A')}")
    print(f"  • Order Management: {config.get('order_mgmt_runtime_arn', 'N/A')}")
    print(f"  • Personalization: {config.get('personalization_runtime_arn', 'N/A')}")
    print(f"  • Product Recommendation: {config.get('product_recommendation_runtime_arn', 'N/A')}")
    print(f"  • Troubleshooting: {config.get('troubleshooting_runtime_arn', 'N/A')}")
    print(f"\nGateways:")
    print(f"  • Order Management: {config.get('order_mgmt_gateway_id', 'N/A')}")
    print(f"  • Personalization: {config.get('personalization_gateway_id', 'N/A')}")
    print(f"  • Product (Sponsored): {config.get('product_recommendation_sponsored_gateway_id', 'N/A')}")
    print(f"  • Product (Organic): {config.get('product_recommendation_organic_gateway_id', 'N/A')}")
    print(f"  • Troubleshooting: {config.get('troubleshooting_gateway_id', 'N/A')}")
    print(f"\nKnowledge Bases:")
    print(f"  • Personalization: {config.get('kb_id', 'N/A')}")
    print(f"  • Troubleshooting: {config.get('troubleshooting_kb_id', 'N/A')}")
    print(f"\nCognito:")
    print(f"  • User Pool: {config.get('cognito_user_pool_id', 'N/A')}")
    print(f"  • Client ID: {config.get('cognito_client_id', 'N/A')}")
    print(f"\nMemory:")
    print(f"  • Memory ID: {config.get('memory_id', 'N/A')}")
    print(f"\nTest User:")
    print(f"  • Username: {config.get('test_user', {}).get('username', 'N/A')}")
    print(f"  • Customer ID: {config.get('test_user', {}).get('customer_id', 'N/A')}")


def main() -> int:
    """
    Main setup function.
    
    Returns:
        0 for success, 1 for failure
    """
    print("=" * 60)
    print("Test Setup: Extracting Configuration")
    print("=" * 60)
    
    try:
        region = os.environ.get('AWS_REGION', 'us-east-1')
        print(f"Region: {region}\n")
        
        # Collect stack outputs
        config = collect_stack_outputs(region)
        
        # Create test user
        config = setup_test_user(config)
        
        # Validate configuration
        is_valid, missing_fields = validate_config(config)
        if not is_valid:
            print("\n" + "=" * 60)
            print("⚠ Configuration Incomplete!")
            print("=" * 60)
            print("\nMissing required fields:")
            for field in missing_fields:
                print(f"  • {field}")
            print("\nPlease ensure all stacks are deployed successfully.")
            return 1
        
        # Save configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_config.json')
        save_config(config, config_path)
        
        # Print summary
        print_config_summary(config)
        
        print("\n" + "=" * 60)
        print("✓ Setup completed successfully!")
        print("=" * 60)
        print(f"\nConfiguration saved to: {config_path}")
        print("\nNext steps:")
        print("  1. Run infrastructure tests: python tests/integration/01_infrastructure/")
        print("  2. Or run all tests: python tests/integration/run_all_tests.py")
        
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("✗ Setup failed!")
        print("=" * 60)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
