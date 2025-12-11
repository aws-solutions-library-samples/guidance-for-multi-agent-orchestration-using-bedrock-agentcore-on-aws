"""
Cognito authentication utilities for JWT token management.
"""

import boto3
from botocore.exceptions import ClientError

from .errors import ErrorCategory, TestError


def create_test_user(
    user_pool_id: str,
    username: str,
    temp_password: str,
    region: str = 'us-east-1'
) -> None:
    """
    Create a test user in Cognito User Pool.
    
    Args:
        user_pool_id: Cognito User Pool ID
        username: Username/email for the test user
        temp_password: Temporary password (user will be forced to change)
        region: AWS region (default: us-east-1)
        
    Raises:
        TestError: If user creation fails (except when user already exists)
    """
    try:
        cognito = boto3.client('cognito-idp', region_name=region)
        
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=username,
            TemporaryPassword=temp_password,
            MessageAction='SUPPRESS'  # Don't send email
        )
        
        print(f"✓ Created test user: {username}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'UsernameExistsException':
            print(f"✓ Test user already exists: {username}")
        else:
            raise TestError(
                ErrorCategory.AUTHENTICATION,
                f"Failed to create test user: {str(e)}",
                {'username': username, 'error': str(e)}
            )


def get_jwt_token(
    user_pool_id: str,
    client_id: str,
    username: str,
    password: str,
    region: str = 'us-east-1'
) -> str:
    """
    Authenticate with Cognito and return JWT AccessToken.
    
    Uses AWS Cognito InitiateAuth with ADMIN_NO_SRP_AUTH flow.
    Handles NEW_PASSWORD_REQUIRED challenge if needed.
    
    Args:
        user_pool_id: Cognito User Pool ID
        client_id: Cognito App Client ID
        username: User's username/email
        password: User's password
        region: AWS region (default: us-east-1)
        
    Returns:
        JWT AccessToken string
        
    Raises:
        TestError: If authentication fails
    """
    try:
        cognito = boto3.client('cognito-idp', region_name=region)
        
        response = cognito.admin_initiate_auth(
            UserPoolId=user_pool_id,
            ClientId=client_id,
            AuthFlow='ADMIN_NO_SRP_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        # Handle NEW_PASSWORD_REQUIRED challenge
        if 'ChallengeName' in response and response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
            # Set the same password as permanent
            response = cognito.admin_respond_to_auth_challenge(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                ChallengeName='NEW_PASSWORD_REQUIRED',
                ChallengeResponses={
                    'USERNAME': username,
                    'PASSWORD': password,
                    'NEW_PASSWORD': password
                },
                Session=response['Session']
            )
        
        if 'AuthenticationResult' not in response:
            raise TestError(
                ErrorCategory.AUTHENTICATION,
                "Authentication did not return tokens",
                {'username': username}
            )
        
        # Return AccessToken instead of IdToken for AgentCore Runtime authentication
        # AgentCore expects access tokens with proper client_id claim
        return response['AuthenticationResult']['AccessToken']
        
    except ClientError as e:
        raise TestError(
            ErrorCategory.AUTHENTICATION,
            f"Authentication failed: {str(e)}",
            {'username': username, 'error': str(e)}
        )
