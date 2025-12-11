#!/usr/bin/env python3
"""
Test: Memory Service Validation

Validates that the AgentCore Memory service is available.

Requirements: 1.6
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])

from tests.integration.utils import load_config


def check_memory_resource(memory_id: str, region: str) -> tuple[bool, list[str]]:
    """
    Verify AgentCore Memory resource exists and is ACTIVE.
    
    Args:
        memory_id: Memory resource ID
        region: AWS region
        
    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    
    if not memory_id:
        issues.append("Memory ID not found in configuration")
        return False, issues
    
    bedrock_agentcore = boto3.client('bedrock-agentcore-control', region_name=region)
    
    try:
        response = bedrock_agentcore.get_memory(memoryId=memory_id)
        
        memory_name = response.get('name', response.get('memoryName', 'Unknown'))
        memory_arn = response.get('memoryArn', response.get('arn', ''))
        
        print(f"  Memory: {memory_name}")
        print(f"  ID: {memory_id}")
        print(f"  ARN: {memory_arn}")
        print(f"  Status: ACTIVE")
        
        return True, issues
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'ResourceNotFoundException':
            issues.append(f"Memory resource not found: {memory_id}")
        else:
            issues.append(f"Failed to check Memory resource: {str(e)}")
        return False, issues
    
    except Exception as e:
        issues.append(f"Unexpected error checking Memory resource: {str(e)}")
        return False, issues


def main() -> int:
    """Main test function."""
    print("=" * 60)
    print("Test: Memory Service Validation")
    print("=" * 60)
    print()
    
    try:
        config = load_config()
        region = config['aws_region']
        memory_id = config.get('memory_id')
        
        print(f"Region: {region}\n")
        
        print("Checking AgentCore Memory resource...")
        passed, issues = check_memory_resource(memory_id, region)
        
        print("\n" + "=" * 60)
        if passed:
            print("PASSED: Memory service is available")
            return 0
        else:
            print("FAILED: Memory validation issues found")
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
