#!/usr/bin/env python3
"""
Fix all AgentCore Runtimes to enable Authorization header pass-through.

This script configures AgentCore runtimes to allow extraction of JWT tokens from
the Authorization header. This is required for agent-to-agent communication where
sub-agents need to validate and extract user identity from JWT tokens.

WHEN IT'S USED:
- Automatically called by deploy-complete-system.sh after stack deployment
- Can be run manually if authorization headers need to be reconfigured

WHAT IT DOES:
- Finds all runtime ARNs from CloudFormation stack outputs
- Adds 'Authorization' to the allowedRequestHeaders list for each runtime
- Enables agents to access JWT tokens via context.request_headers

PREREQUISITES:
- AgentCore runtimes must be deployed via CDK stacks
- AWS credentials configured with bedrock-agentcore permissions

USAGE:
    python fix_all_runtime_auth.py --region us-east-1 --profile my-profile
    python fix_all_runtime_auth.py --region us-west-2  # Uses default profile
"""

import argparse
import boto3
import sys
from typing import List, Tuple


def get_runtime_arns(region: str, profile: str = None) -> List[str]:
    """Get all runtime ARNs from CloudFormation stack outputs."""
    session = boto3.Session(profile_name=profile, region_name=region)
    cfn = session.client('cloudformation')
    
    runtime_arns = []
    
    try:
        # Get all stacks
        paginator = cfn.get_paginator('describe_stacks')
        for page in paginator.paginate():
            for stack in page['Stacks']:
                # Look for outputs with 'RuntimeArn' in the key
                if 'Outputs' in stack:
                    for output in stack['Outputs']:
                        if 'RuntimeArn' in output['OutputKey']:
                            runtime_arns.append(output['OutputValue'])
    except Exception as e:
        print(f"Error getting runtime ARNs: {e}")
        return []
    
    return runtime_arns


def fix_runtime_auth(runtime_arn: str, region: str, profile: str = None) -> bool:
    """Update runtime to allow Authorization header."""
    # Extract runtime ID from ARN
    runtime_id = runtime_arn.split('/')[-1]
    
    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client('bedrock-agentcore-control')
    
    try:
        # Get current runtime configuration
        response = client.get_agent_runtime(agentRuntimeId=runtime_id)
        
        # Extract runtime info
        if 'agentRuntime' in response:
            runtime = response['agentRuntime']
        elif 'runtime' in response:
            runtime = response['runtime']
        else:
            runtime = response
        
        # Extract current configuration
        container_uri = runtime['agentRuntimeArtifact']['containerConfiguration']['containerUri']
        role_arn = runtime['roleArn']
        network_mode = runtime.get('networkConfiguration', {}).get('networkMode', 'PUBLIC')
        env_vars = runtime.get('environmentVariables', {})
        authorizer_config = runtime.get('authorizerConfiguration', {})
        
        # Update with Authorization header allowlist
        client.update_agent_runtime(
            agentRuntimeId=runtime_id,
            agentRuntimeArtifact={
                'containerConfiguration': {
                    'containerUri': container_uri
                }
            },
            roleArn=role_arn,
            networkConfiguration={
                'networkMode': network_mode
            },
            protocolConfiguration={
                'serverProtocol': 'HTTP'
            },
            requestHeaderConfiguration={
                'requestHeaderAllowlist': ['Authorization']
            },
            environmentVariables=env_vars,
            authorizerConfiguration=authorizer_config
        )
        
        return True
        
    except client.exceptions.ResourceNotFoundException:
        print(f"  ✗ Runtime not found: {runtime_id}")
        return False
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Fix all AgentCore Runtimes to enable Authorization header pass-through'
    )
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--profile', help='AWS profile name (optional)')
    parser.add_argument('--runtime-arn', help='Fix specific runtime ARN only (optional)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("AgentCore Runtime Authorization Header Fix - Batch Mode")
    print("=" * 80)
    print(f"Region: {args.region}")
    print(f"Profile: {args.profile or '<default>'}")
    print()
    
    # Get runtime ARNs
    if args.runtime_arn:
        runtime_arns = [args.runtime_arn]
        print(f"Fixing specific runtime: {args.runtime_arn}")
    else:
        print("Finding all runtimes from CloudFormation outputs...")
        runtime_arns = get_runtime_arns(args.region, args.profile)
        
        if not runtime_arns:
            print("✗ No runtime ARNs found in CloudFormation outputs")
            sys.exit(1)
        
        print(f"Found {len(runtime_arns)} runtime(s)")
    
    print()
    
    # Fix each runtime
    success_count = 0
    failed_arns = []
    
    for i, arn in enumerate(runtime_arns, 1):
        runtime_name = arn.split('/')[-1]
        print(f"[{i}/{len(runtime_arns)}] {runtime_name}")
        
        if fix_runtime_auth(arn, args.region, args.profile):
            print(f"  ✓ Successfully configured")
            success_count += 1
        else:
            failed_arns.append(arn)
    
    # Summary
    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total runtimes: {len(runtime_arns)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(failed_arns)}")
    
    if failed_arns:
        print()
        print("Failed runtimes:")
        for arn in failed_arns:
            print(f"  - {arn}")
        print()
        print("To retry a specific runtime:")
        print(f"  python {sys.argv[0]} --runtime-arn <ARN> --region {args.region}")
        sys.exit(1)
    else:
        print()
        print("✓ All runtimes configured successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
