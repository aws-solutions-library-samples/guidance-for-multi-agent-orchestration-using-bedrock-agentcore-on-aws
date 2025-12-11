#!/usr/bin/env python3
"""
Setup test users for Customer Support Assistant testing

REQUIRED BEFORE TESTING: This script creates Cognito users needed for JWT authentication
in the supervisor test suite. Must be run after CDK deployment and before running tests.

What it does:
1. Reads Cognito User Pool configuration from CDK stack outputs
2. Creates test users (cust001@example.com, cust002@example.com) with customer_id attributes
3. Saves configuration to test_users_config.json for test scripts to use

PREREQUISITES:
    - CDK stack 'CustomerSupportAssistantStack' must be deployed
    - AWS credentials configured (uses default profile)

USAGE:
    # Create users with password (must meet Cognito requirements: 8+ chars, mixed case, numbers)
    python scripts/setup_test_users.py --password TestPassword123!
    
    # Update config only (if users already exist)
    python scripts/setup_test_users.py --config-only

OUTPUTS:
    - Creates test_users_config.json with Cognito configuration and user credentials
    - Test users can authenticate and receive JWT tokens for agent testing
"""

import boto3
import json
import sys
import argparse
import os
from pathlib import Path

# Configuration
REGION = os.environ.get('AWS_REGION', 'us-east-1')  # Read from environment, falls back to us-east-1 if not set
PROFILE = os.environ.get('AWS_PROFILE')  # Read from environment, falls back to default if not set
STACK_NAME = 'CustomerSupportAssistantStack'
CONFIG_FILE = Path(__file__).parent / f'test_users_config-{REGION}.json'

# Test users to create (password will be set from argument)
# Names selected from AWS Style Guide to match customer database demographics
TEST_USERS = [
    # cust001: 28, male, $70-90k, San Francisco, gold
    {'email': 'mateo_jackson@example.com', 'customer_id': 'cust001', 'given_name': 'Mateo', 'family_name': 'Jackson'},
    # cust002: 32, female, $50-70k, New York, silver
    {'email': 'martha_rivera@example.com', 'customer_id': 'cust002', 'given_name': 'Martha', 'family_name': 'Rivera'},
    # cust003: 24, male, $30-50k, Austin, bronze
    {'email': 'carlos_salazar@example.com', 'customer_id': 'cust003', 'given_name': 'Carlos', 'family_name': 'Salazar'},
    # cust004: 45, male, $100k+, Seattle, platinum
    {'email': 'richard_roe@example.com', 'customer_id': 'cust004', 'given_name': 'Richard', 'family_name': 'Roe'},
    # cust005: 20, female, $20-30k, Boston, bronze
    {'email': 'jane_doe@example.com', 'customer_id': 'cust005', 'given_name': 'Jane', 'family_name': 'Doe'},
    # cust006: 38, female, $70-90k, Chicago, gold
    {'email': 'mary_major@example.com', 'customer_id': 'cust006', 'given_name': 'Mary', 'family_name': 'Major'},
    # cust007: 26, male, $50-70k, Los Angeles, silver
    {'email': 'diego_ramirez@example.com', 'customer_id': 'cust007', 'given_name': 'Diego', 'family_name': 'Ramirez'},
    # cust008: 35, female, $90-100k, Denver, gold
    {'email': 'saanvi_sarkar@example.com', 'customer_id': 'cust008', 'given_name': 'Saanvi', 'family_name': 'Sarkar'},
    # cust009: 29, male, $40-60k, Miami, silver
    {'email': 'jorge_souza@example.com', 'customer_id': 'cust009', 'given_name': 'Jorge', 'family_name': 'Souza'},
    # cust010: 41, female, $80-100k, Portland, platinum
    {'email': 'shirley_rodriguez@example.com', 'customer_id': 'cust010', 'given_name': 'Shirley', 'family_name': 'Rodriguez'}
]

def get_cdk_outputs():
    """Get CDK stack outputs."""
    print(f"📦 Reading CDK outputs from stack: {STACK_NAME}")
    
    session = boto3.Session(region_name=REGION) if PROFILE is None else boto3.Session(profile_name=PROFILE, region_name=REGION)
    cfn = session.client('cloudformation')
    
    try:
        response = cfn.describe_stacks(StackName=STACK_NAME)
        outputs = response['Stacks'][0]['Outputs']
        
        config = {}
        for output in outputs:
            key = output['OutputKey']
            value = output['OutputValue']
            
            if 'UserPoolId' in key:
                config['user_pool_id'] = value
            elif 'ClientId' in key:
                config['client_id'] = value
            elif 'SupervisorAgentRuntimeArn' in key:
                config['runtime_arn'] = value
        
        if not all(k in config for k in ['user_pool_id', 'client_id', 'runtime_arn']):
            print("❌ Missing required CDK outputs. Stack may not be deployed.")
            print(f"   Found: {list(config.keys())}")
            sys.exit(1)
        
        print(f"✅ Found CDK outputs:")
        print(f"   User Pool ID: {config['user_pool_id']}")
        print(f"   Client ID: {config['client_id']}")
        print(f"   Runtime ARN: {config['runtime_arn']}")
        
        return config
        
    except Exception as e:
        print(f"❌ Failed to read CDK outputs: {e}")
        print(f"   Make sure stack '{STACK_NAME}' is deployed")
        sys.exit(1)

def create_user(cognito, user_pool_id, user, password):
    """Create a Cognito user with customer_id attribute, or update password if user exists."""
    email = user['email']
    customer_id = user['customer_id']
    print(f"\n👤 Creating user: {email} (customer_id: {customer_id})")
    
    try:
        # Check if user already exists
        user_exists = False
        try:
            cognito.admin_get_user(
                UserPoolId=user_pool_id,
                Username=email
            )
            user_exists = True
            print(f"   ℹ️  User already exists, updating password...")
        except cognito.exceptions.UserNotFoundException:
            pass
        
        if user_exists:
            # Update password for existing user
            cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=email,
                Password=password,
                Permanent=True
            )
            print(f"   ✅ Password updated successfully")
            return True
        
        # Create new user
        # Build user attributes
        user_attributes = [
            {'Name': 'email', 'Value': email},
            {'Name': 'custom:customer_id', 'Value': customer_id}
        ]
        
        # Add optional name attributes if provided
        if 'given_name' in user:
            user_attributes.append({'Name': 'given_name', 'Value': user['given_name']})
        if 'family_name' in user:
            user_attributes.append({'Name': 'family_name', 'Value': user['family_name']})
        
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            TemporaryPassword=password,
            UserAttributes=user_attributes,
            MessageAction='SUPPRESS'
        )
        
        # Set permanent password
        cognito.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=email,
            Password=password,
            Permanent=True
        )
        
        print(f"   ✅ User created successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create/update user: {e}")
        return False

def save_config(cdk_config, users, password):
    """Save configuration for test scripts."""
    config = {
        'region': REGION,
        'profile': PROFILE or 'default',
        'user_pool_id': cdk_config['user_pool_id'],
        'client_id': cdk_config['client_id'],
        'runtime_arn': cdk_config['runtime_arn'],
        'users': [{'email': u['email'], 'customer_id': u['customer_id'], 'password': password} for u in users]
    }
    
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"\n💾 Configuration saved to: {CONFIG_FILE}")
    print(f"   Test scripts can now use this configuration")

def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description='Setup test users for Customer Support Assistant')
    parser.add_argument('--password', required=False, help='Password for test users (must meet Cognito requirements)')
    parser.add_argument('--config-only', action='store_true', help='Only update configuration with current CDK outputs')
    parser.add_argument('--profile', help='AWS profile name (optional, uses default if not specified)')
    args = parser.parse_args()
    
    # Set global PROFILE from argument
    global PROFILE
    if args.profile:
        PROFILE = args.profile
    
    if not args.config_only and not args.password:
        parser.error('--password is required unless using --config-only')
    
    print("=" * 70)
    print("Customer Support Assistant - Test User Setup")
    print("=" * 70)
    
    # Get CDK outputs
    cdk_config = get_cdk_outputs()
    
    if args.config_only:
        # Load existing users from config
        existing_config = json.loads(CONFIG_FILE.read_text())
        save_config(cdk_config, existing_config['users'], existing_config['users'][0]['password'])
        print("✅ Configuration updated with current CDK outputs")
        return
    
    # Create Cognito client
    session = boto3.Session(region_name=REGION) if PROFILE is None else boto3.Session(profile_name=PROFILE, region_name=REGION)
    cognito = session.client('cognito-idp')
    
    # Create users
    print("\n📝 Creating test users...")
    success_count = 0
    for user in TEST_USERS:
        if create_user(cognito, cdk_config['user_pool_id'], user, args.password):
            success_count += 1
    
    # Save configuration
    save_config(cdk_config, TEST_USERS, args.password)
    
    # Summary
    print("\n" + "=" * 70)
    print(f"✅ Setup complete: {success_count}/{len(TEST_USERS)} users ready")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Run test script: python scripts/test_supervisor.py")
    print("  2. Add more users by editing TEST_USERS in this script")
    print("=" * 70)

if __name__ == '__main__':
    main()
