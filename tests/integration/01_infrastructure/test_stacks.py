#!/usr/bin/env python3
"""
Test: CloudFormation Stacks Validation

Validates that all required CloudFormation stacks exist and are in successful status.

Requirements: 1.1
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])

from tests.integration.utils import load_config


def check_stacks(region: str) -> tuple[bool, list[str]]:
    """
    Verify CDK stacks exist and are in successful status.
    
    Args:
        region: AWS region
        
    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    stacks = [
        'KnowledgeBaseStack',
        'CustomerSupportAssistantStack',
        'OrderManagementAgentStack',
        'PersonalizationAgentStack'
    ]
    
    cfn = boto3.client('cloudformation', region_name=region)
    
    for stack_name in stacks:
        try:
            response = cfn.describe_stacks(StackName=stack_name)
            status = response['Stacks'][0]['StackStatus']
            
            print(f"  {stack_name}: {status}")
            
            if status not in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                issues.append(f"{stack_name} is not in successful status: {status}")
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'ValidationError':
                issues.append(f"{stack_name} does not exist")
            else:
                issues.append(f"Failed to check {stack_name}: {str(e)}")
        except Exception as e:
            issues.append(f"Unexpected error checking {stack_name}: {str(e)}")
    
    return len(issues) == 0, issues


def main() -> int:
    """Main test function."""
    print("=" * 60)
    print("Test: CloudFormation Stacks Validation")
    print("=" * 60)
    print()
    
    try:
        config = load_config()
        region = config['aws_region']
        print(f"Region: {region}\n")
        
        print("Checking CloudFormation stacks...")
        passed, issues = check_stacks(region)
        
        print("\n" + "=" * 60)
        if passed:
            print("PASSED: All stacks are in successful status")
            return 0
        else:
            print("FAILED: Stack validation issues found")
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
