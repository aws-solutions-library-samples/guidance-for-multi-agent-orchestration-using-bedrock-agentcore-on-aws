"""
AgentCore Runtime invocation utilities.
"""

import json
import urllib.parse
from typing import Any, Dict, Tuple

import requests

from .errors import ErrorCategory, TestError


def extract_runtime_endpoint(runtime_arn: str, region: str) -> str:
    """
    Extract Runtime endpoint URL from ARN.
    
    Args:
        runtime_arn: Runtime ARN
        region: AWS region
        
    Returns:
        Runtime endpoint URL
    """
    encoded_arn = urllib.parse.quote(runtime_arn, safe='')
    agentcore_endpoint = f"https://bedrock-agentcore.{region}.amazonaws.com"
    runtime_endpoint = f"{agentcore_endpoint}/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    return runtime_endpoint


def invoke_runtime(
    runtime_endpoint: str,
    payload: Dict[str, Any],
    jwt: str,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Invoke an AgentCore Runtime with JWT authentication.
    
    Args:
        runtime_endpoint: Runtime HTTP endpoint URL
        payload: Request payload dictionary
        jwt: JWT token for Authorization header
        timeout: Request timeout in seconds (default: 30)
        
    Returns:
        Dictionary with 'status_code' and 'body' keys
        
    Raises:
        TestError: If invocation fails
    """
    try:
        headers = {
            'Authorization': f'Bearer {jwt}',
            'Content-Type': 'application/json',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
        }
        
        response = requests.post(
            runtime_endpoint,
            json=payload,
            headers=headers,
            timeout=timeout
        )
        
        return {
            'status_code': response.status_code,
            'body': response.json() if response.content else {}
        }
        
    except requests.exceptions.Timeout:
        raise TestError(
            ErrorCategory.RUNTIME,
            f"Runtime invocation timed out after {timeout}s",
            {'endpoint': runtime_endpoint}
        )
    except requests.exceptions.RequestException as e:
        raise TestError(
            ErrorCategory.RUNTIME,
            f"Runtime invocation failed: {str(e)}",
            {'endpoint': runtime_endpoint, 'error': str(e)}
        )


def invoke_agentcore_runtime(
    runtime_arn: str = None,
    runtime_endpoint: str = None,
    jwt: str = None,
    customer_id: str = None,
    session_id: str = None,
    prompt: str = None,
    query: str = None,
    region: str = 'us-east-1',
    timeout: int = 60
) -> Tuple[bool, int, Dict[str, Any]]:
    """
    Invoke AgentCore Runtime with query.
    
    Args:
        runtime_arn: Runtime ARN (will extract endpoint from this)
        runtime_endpoint: Runtime HTTP endpoint URL (alternative to runtime_arn)
        jwt: JWT token for Authorization header
        customer_id: Customer ID for the request
        session_id: Session ID for the request
        prompt: Prompt/query string (alternative name for query)
        query: Query string (alternative name for prompt)
        region: AWS region (used if runtime_arn is provided)
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (success, status_code, response_body)
    """
    # Handle parameter aliases
    if runtime_arn and not runtime_endpoint:
        runtime_endpoint = extract_runtime_endpoint(runtime_arn, region)
    
    if query and not prompt:
        prompt = query
    
    if not runtime_endpoint:
        raise ValueError("Either runtime_arn or runtime_endpoint must be provided")
    if not jwt:
        raise ValueError("jwt is required")
    if not customer_id:
        raise ValueError("customer_id is required")
    if not session_id:
        raise ValueError("session_id is required")
    if not prompt:
        raise ValueError("prompt or query is required")
    
    try:
        headers = {
            'Authorization': f'Bearer {jwt}',
            'Content-Type': 'application/json',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
        }
        
        # Determine payload field based on agent type
        # Supervisor expects 'prompt', sub-agents expect 'query'
        is_supervisor = 'supervisor' in runtime_arn.lower() if runtime_arn else 'supervisor' in runtime_endpoint.lower()
        
        payload = {
            'customer_id': customer_id,
            'session_id': session_id,
            'prompt' if is_supervisor else 'query': prompt
        }
        
        print(f"  Invoking Runtime endpoint: {runtime_endpoint}")
        print(f"  Prompt: {prompt}")
        
        response = requests.post(
            runtime_endpoint,
            json=payload,
            headers=headers,
            timeout=timeout
        )
        
        print(f"  Response status: {response.status_code}")
        
        if response.status_code >= 400:
            print(f"  Error response: {response.text[:500]}")
        
        response_body = {}
        if response.content:
            try:
                response_body = response.json()
            except json.JSONDecodeError:
                response_body = {'raw_content': response.text}
        
        return (response.status_code == 200, response.status_code, response_body)
        
    except requests.exceptions.Timeout:
        print(f"  Request timed out after {timeout}s")
        return (False, 0, {'error': 'timeout'})
    except requests.exceptions.RequestException as e:
        print(f"  Request failed: {str(e)}")
        return (False, 0, {'error': str(e)})
