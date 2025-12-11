#!/usr/bin/env python3
"""
Test: Gateways Validation

Validates that all Gateways are ACTIVE with expected targets configured.

Requirements: 1.3
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])

from tests.integration.utils import load_config


def check_gateways(config: dict) -> tuple[bool, list[str]]:
    """
    Verify Gateways are active with targets.
    
    Args:
        config: Test configuration dictionary
        
    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    client = boto3.client('bedrock-agentcore-control', region_name=config['aws_region'])
    
    gateways = {
        'Order Management': {
            'id': config.get('order_mgmt_gateway_id'),
            'expected_targets': ['orders', 'inventory']
        },
        'Personalization': {
            'id': config.get('personalization_gateway_id'),
            'expected_targets': ['customer-database', 'browsing-kb']
        },
        'Product Recommendation (Sponsored)': {
            'id': config.get('product_recommendation_sponsored_gateway_id'),
            'expected_targets': ['sponsored-products']
        },
        'Product Recommendation (Organic)': {
            'id': config.get('product_recommendation_organic_gateway_id'),
            'expected_targets': ['organic-products']
        },
        'Troubleshooting': {
            'id': config.get('troubleshooting_gateway_id'),
            'expected_targets': ['kb-query']
        }
    }
    
    for name, gateway_info in gateways.items():
        gateway_id = gateway_info['id']
        expected_targets = gateway_info['expected_targets']
        
        if not gateway_id:
            issues.append(f"{name} gateway ID not found in configuration")
            continue
        
        try:
            # Check gateway status
            response = client.get_gateway(gatewayIdentifier=gateway_id)
            status = response.get('status')
            
            print(f"  {name} Gateway: {status}")
            
            if status not in ['ACTIVE', 'READY']:
                issues.append(f"{name} gateway is not active: {status}")
            
            # Check gateway targets
            targets_response = client.list_gateway_targets(gatewayIdentifier=gateway_id)
            target_names = [t['name'] for t in targets_response.get('items', [])]
            
            print(f"    Targets: {', '.join(target_names)}")
            
            for target in expected_targets:
                if target not in target_names:
                    issues.append(f"{name} gateway missing target: {target}")
                    
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'ResourceNotFoundException':
                issues.append(f"{name} gateway not found: {gateway_id}")
            else:
                issues.append(f"Failed to check {name} gateway: {str(e)}")
        except Exception as e:
            issues.append(f"Unexpected error checking {name} gateway: {str(e)}")
    
    return len(issues) == 0, issues


def main() -> int:
    """Main test function."""
    print("=" * 60)
    print("Test: Gateways Validation")
    print("=" * 60)
    print()
    
    try:
        config = load_config()
        print(f"Region: {config['aws_region']}\n")
        
        print("Checking Gateways...")
        passed, issues = check_gateways(config)
        
        print("\n" + "=" * 60)
        if passed:
            print("PASSED: All gateways are active with expected targets")
            return 0
        else:
            print("FAILED: Gateway validation issues found")
            print("=" * 60)
            print("\nIssues:")
            for issue in issues:
                print(f"  - {issue}")
            return 1
            
    except FileNotFoundError as e:
        print(f"ERROR: {str(e)}")
        print("Run tests/integration/00_setup/test_setup.py first")
        return 1
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
