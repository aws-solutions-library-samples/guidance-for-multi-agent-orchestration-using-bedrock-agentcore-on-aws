#!/usr/bin/env python3
"""
Test: Cognito Configuration Validation

Validates that Cognito User Pool and App Client are properly configured.

Requirements: 1.5
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])

from tests.integration.utils import load_config


def validate_cognito(config: dict) -> tuple[bool, list[str]]:
    """
    Validate Cognito User Pool and App Client configuration.
    
    Args:
        config: Test configuration dictionary
        
    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    user_pool_id = config.get('cognito_user_pool_id')
    client_id = config.get('cognito_client_id')
    region = config['aws_region']
    
    if not user_pool_id:
        issues.append("User Pool ID not found in configuration")
        return False, issues
    
    if not client_id:
        issues.append("App Client ID not found in configuration")
        return False, issues
    
    cognito = boto3.client('cognito-idp', region_name=region)
    
    # Check User Pool exists
    try:
        response = cognito.describe_user_pool(UserPoolId=user_pool_id)
        pool_name = response['UserPool']['Name']
        print(f"  User Pool: {pool_name}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'ResourceNotFoundException':
            issues.append(f"User Pool not found: {user_pool_id}")
        else:
            issues.append(f"Failed to check User Pool: {str(e)}")
        return False, issues
    except Exception as e:
        issues.append(f"Unexpected error checking User Pool: {str(e)}")
        return False, issues
    
    # Check App Client has required auth flow
    try:
        response = cognito.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id
        )
        client_info = response['UserPoolClient']
        client_name = client_info['ClientName']
        auth_flows = client_info.get('ExplicitAuthFlows', [])
        
        print(f"  App Client: {client_name}")
        print(f"  Auth Flows: {', '.join(auth_flows)}")
        
        has_admin_auth = (
            'ADMIN_NO_SRP_AUTH' in auth_flows or 
            'ALLOW_ADMIN_USER_PASSWORD_AUTH' in auth_flows
        )
        
        if not has_admin_auth:
            issues.append("App Client missing required auth flow: ADMIN_NO_SRP_AUTH or ALLOW_ADMIN_USER_PASSWORD_AUTH")
            return False, issues
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'ResourceNotFoundException':
            issues.append(f"App Client not found: {client_id}")
        else:
            issues.append(f"Failed to check App Client: {str(e)}")
        return False, issues
    except Exception as e:
        issues.append(f"Unexpected error checking App Client: {str(e)}")
        return False, issues
    
    return True, issues


def main() -> int:
    """Main test function."""
    print("=" * 60)
    print("Test: Cognito Configuration Validation")
    print("=" * 60)
    print()
    
    try:
        config = load_config()
        print(f"Region: {config['aws_region']}\n")
        
        print("Checking Cognito configuration...")
        passed, issues = validate_cognito(config)
        
        print("\n" + "=" * 60)
        if passed:
            print("PASSED: Cognito is properly configured")
            return 0
        else:
            print("FAILED: Cognito validation issues found")
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
