#!/usr/bin/env python3
"""
Test: AgentCore Runtimes Validation

Validates that all AgentCore Runtimes are in ACTIVE/READY status.

Requirements: 1.2
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])

from tests.integration.utils import load_config


def check_runtimes(config: dict) -> tuple[bool, list[str]]:
    """
    Verify AgentCore Runtimes are ready.
    
    Args:
        config: Test configuration dictionary
        
    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    client = boto3.client('bedrock-agentcore-control', region_name=config['aws_region'])
    
    runtimes = {
        'Supervisor': config.get('supervisor_runtime_arn'),
        'Order Management': config.get('order_mgmt_runtime_arn'),
        'Personalization': config.get('personalization_runtime_arn'),
        'Product Recommendation': config.get('product_recommendation_runtime_arn'),
        'Troubleshooting': config.get('troubleshooting_runtime_arn')
    }
    
    for name, arn in runtimes.items():
        if not arn:
            issues.append(f"{name} runtime ARN not found in configuration")
            continue
            
        try:
            runtime_id = arn.split('/')[-1]
            response = client.get_agent_runtime(agentRuntimeId=runtime_id)
            status = response.get('status')
            
            print(f"  {name}: {status}")
            
            if status not in ['ACTIVE', 'AVAILABLE', 'READY']:
                issues.append(f"{name} runtime is not ready: {status}")
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'ResourceNotFoundException':
                issues.append(f"{name} runtime not found: {runtime_id}")
            else:
                issues.append(f"Failed to check {name} runtime: {str(e)}")
        except Exception as e:
            issues.append(f"Unexpected error checking {name} runtime: {str(e)}")
    
    return len(issues) == 0, issues


def main() -> int:
    """Main test function."""
    print("=" * 60)
    print("Test: AgentCore Runtimes Validation")
    print("=" * 60)
    print()
    
    try:
        config = load_config()
        print(f"Region: {config['aws_region']}\n")
        
        print("Checking AgentCore Runtimes...")
        passed, issues = check_runtimes(config)
        
        print("\n" + "=" * 60)
        if passed:
            print("PASSED: All runtimes are ready")
            return 0
        else:
            print("FAILED: Runtime validation issues found")
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
