"""
AWS operations utilities for CloudFormation, AgentCore, and other AWS services.
"""

from typing import Dict, List, Tuple

import boto3
from botocore.exceptions import ClientError

from .errors import ErrorCategory, TestError


def extract_stack_outputs(stack_name: str, region: str = 'us-east-1') -> Dict[str, str]:
    """
    Query CloudFormation stack outputs and return as dictionary.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region (default: us-east-1)
        
    Returns:
        Dictionary mapping output keys to values
        
    Raises:
        TestError: If stack doesn't exist or query fails
    """
    try:
        cfn = boto3.client('cloudformation', region_name=region)
        response = cfn.describe_stacks(StackName=stack_name)
        
        if not response['Stacks']:
            raise TestError(
                ErrorCategory.INFRASTRUCTURE,
                f"Stack {stack_name} not found",
                {'stack_name': stack_name, 'region': region}
            )
        
        stack = response['Stacks'][0]
        outputs = {}
        
        if 'Outputs' in stack:
            for output in stack['Outputs']:
                outputs[output['OutputKey']] = output['OutputValue']
        
        return outputs
        
    except ClientError as e:
        raise TestError(
            ErrorCategory.INFRASTRUCTURE,
            f"Failed to query stack {stack_name}: {str(e)}",
            {'stack_name': stack_name, 'error': str(e)}
        )


def check_stack_status(stack_name: str, region: str = 'us-east-1') -> str:
    """
    Get CloudFormation stack status.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region (default: us-east-1)
        
    Returns:
        Stack status string (CREATE_COMPLETE, UPDATE_COMPLETE, etc.)
        
    Raises:
        TestError: If stack doesn't exist or query fails
    """
    try:
        cfn = boto3.client('cloudformation', region_name=region)
        response = cfn.describe_stacks(StackName=stack_name)
        
        if not response['Stacks']:
            raise TestError(
                ErrorCategory.INFRASTRUCTURE,
                f"Stack {stack_name} not found",
                {'stack_name': stack_name, 'region': region}
            )
        
        return response['Stacks'][0]['StackStatus']
        
    except ClientError as e:
        raise TestError(
            ErrorCategory.INFRASTRUCTURE,
            f"Failed to check stack status: {str(e)}",
            {'stack_name': stack_name, 'error': str(e)}
        )


def check_runtime_status(runtime_arn: str, region: str = 'us-east-1') -> str:
    """
    Get AgentCore Runtime status.
    
    Args:
        runtime_arn: Runtime ARN
        region: AWS region (default: us-east-1)
        
    Returns:
        Runtime status string (ACTIVE, READY, CREATING, etc.)
        
    Raises:
        TestError: If status check fails
    """
    try:
        bedrock = boto3.client('bedrock-agentcore', region_name=region)
        
        response = bedrock.get_agent_runtime(agentRuntimeArn=runtime_arn)
        return response['agentRuntime']['status']
        
    except ClientError as e:
        raise TestError(
            ErrorCategory.RUNTIME,
            f"Failed to check runtime status: {str(e)}",
            {'runtime_arn': runtime_arn, 'error': str(e)}
        )


def check_gateway_status(gateway_id: str, region: str = 'us-east-1') -> Tuple[str, List[str]]:
    """
    Get AgentCore Gateway status and list of targets.
    
    Args:
        gateway_id: Gateway ID
        region: AWS region (default: us-east-1)
        
    Returns:
        Tuple of (status, list_of_target_ids)
        
    Raises:
        TestError: If status check fails
    """
    try:
        bedrock = boto3.client('bedrock-agentcore', region_name=region)
        
        response = bedrock.get_gateway(gatewayId=gateway_id)
        gateway = response['gateway']
        
        status = gateway.get('status', 'UNKNOWN')
        targets = gateway.get('targets', [])
        target_ids = [target.get('targetId', '') for target in targets]
        
        return (status, target_ids)
        
    except ClientError as e:
        raise TestError(
            ErrorCategory.GATEWAY,
            f"Failed to check gateway status: {str(e)}",
            {'gateway_id': gateway_id, 'error': str(e)}
        )


def check_knowledge_base_status(kb_id: str, region: str = 'us-east-1') -> str:
    """
    Get Knowledge Base status.
    
    Args:
        kb_id: Knowledge Base ID
        region: AWS region (default: us-east-1)
        
    Returns:
        Knowledge Base status string (ACTIVE, CREATING, etc.)
        
    Raises:
        TestError: If status check fails
    """
    try:
        bedrock = boto3.client('bedrock-agent', region_name=region)
        
        response = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)
        return response['knowledgeBase']['status']
        
    except ClientError as e:
        raise TestError(
            ErrorCategory.KNOWLEDGE_BASE,
            f"Failed to check knowledge base status: {str(e)}",
            {'kb_id': kb_id, 'error': str(e)}
        )
