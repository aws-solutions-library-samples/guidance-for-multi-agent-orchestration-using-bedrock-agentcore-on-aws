#!/usr/bin/env python3
"""
Test: Knowledge Bases Validation

Validates that both personalization and troubleshooting Knowledge Bases are ACTIVE.

Requirements: 1.4
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])

from tests.integration.utils import load_config


def check_kb(kb_id: str, kb_name: str, region: str) -> tuple[bool, list[str]]:
    """
    Verify Knowledge Base is active.
    
    Args:
        kb_id: Knowledge Base ID
        kb_name: Name for display purposes
        region: AWS region
        
    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    
    if not kb_id:
        issues.append(f"{kb_name} Knowledge Base ID not found in configuration")
        return False, issues
    
    client = boto3.client('bedrock-agent', region_name=region)
    
    try:
        response = client.get_knowledge_base(knowledgeBaseId=kb_id)
        kb = response.get('knowledgeBase', {})
        
        name = kb.get('name', 'Unknown')
        status = kb.get('status', 'UNKNOWN')
        
        print(f"  {kb_name}: {name} - {status}")
        
        if status != 'ACTIVE':
            issues.append(f"{kb_name} Knowledge Base is not ACTIVE: {status}")
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'ResourceNotFoundException':
            issues.append(f"{kb_name} Knowledge Base not found: {kb_id}")
        else:
            issues.append(f"Failed to check {kb_name} Knowledge Base: {str(e)}")
    except Exception as e:
        issues.append(f"Unexpected error checking {kb_name} Knowledge Base: {str(e)}")
    
    return len(issues) == 0, issues


def main() -> int:
    """Main test function."""
    print("=" * 60)
    print("Test: Knowledge Bases Validation")
    print("=" * 60)
    print()
    
    try:
        config = load_config()
        region = config['aws_region']
        print(f"Region: {region}\n")
        
        print("Checking Knowledge Bases...")
        
        all_passed = True
        all_issues = []
        
        # Check personalization KB
        kb_id = config.get('kb_id')
        passed, issues = check_kb(kb_id, 'Personalization', region)
        all_passed = all_passed and passed
        all_issues.extend(issues)
        
        # Check troubleshooting KB
        troubleshooting_kb_id = config.get('troubleshooting_kb_id')
        passed, issues = check_kb(troubleshooting_kb_id, 'Troubleshooting', region)
        all_passed = all_passed and passed
        all_issues.extend(issues)
        
        print("\n" + "=" * 60)
        if all_passed:
            print("PASSED: All Knowledge Bases are active")
            return 0
        else:
            print("FAILED: Knowledge Base validation issues found")
            print("=" * 60)
            print("\nIssues:")
            for issue in all_issues:
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
