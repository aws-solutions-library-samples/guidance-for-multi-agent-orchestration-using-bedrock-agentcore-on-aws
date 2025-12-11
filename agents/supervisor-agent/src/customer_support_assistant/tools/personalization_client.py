"""
Personalization Agent Client Tool

Invokes the personalization agent runtime for customer-specific queries.
Uses AgentCore Workload Identity for agent-to-agent authentication.
"""

import os
import json
import boto3
from strands import tool, ToolContext


@tool(context=True)
def personalization_agent_tool(query: str, tool_context: ToolContext) -> str:
    """
    Get customer preferences, browsing history, and behavioral insights to inform personalized experiences.
    
    Args:
        query: The personalization query to send to the agent
        
    Returns:
        Response from the personalization agent or structured error message
    """
    try:
        # Get customer_id and session_id from agent state
        customer_id = tool_context.agent.state.get("customer_id")
        if not customer_id:
            return "Unable to retrieve personalized recommendations: Customer ID not available"
        
        
        # Get JWT token from agent state (proper Strands approach)
        jwt_token = tool_context.agent.state.get("jwt_token")
        
        if not jwt_token:
            return "Unable to retrieve personalized recommendations: Authentication token not available"
        
        # Get session_id from agent state and append agent suffix for unique memory namespace
        base_session_id = tool_context.agent.state.get("session_id")
        if not base_session_id:
            import uuid
            base_session_id = str(uuid.uuid4())
        
        # Append agent identifier for memory isolation
        session_id = f"{base_session_id}-personalization"
        
        # Get configuration from SSM Parameter Store
        runtime_id = _get_configuration()
        
        # Use HTTP request for JWT authentication (as per AWS docs)
        # "Since boto3 doesn't support invocation with bearer tokens, you'll need to use an HTTP client"
        import requests
        import urllib.parse
        
        # Initialize AWS clients
        region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Get current account ID dynamically
        sts_client = boto3.client('sts', region_name=region)
        account_id = sts_client.get_caller_identity()['Account']
        
        # Construct AgentCore endpoint URL
        agentcore_endpoint = f'https://bedrock-agentcore.{region}.amazonaws.com'
        runtime_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{runtime_id}"
        escaped_arn = urllib.parse.quote(runtime_arn, safe='')
        url = f"{agentcore_endpoint}/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"
        
        headers = {
            'Authorization': jwt_token,  # JWT token already includes "Bearer " prefix
            'Content-Type': 'application/json',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
        }
        
        payload = json.dumps({
            'query': query,
            'customer_id': customer_id,
            'session_id': session_id,
            'jwt_token': jwt_token  # Pass JWT token in payload as workaround for header pass-through
        })
        
        response = requests.post(url, headers=headers, data=payload, timeout=120)
        
        if response.status_code == 200:
            return response.text
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            return f"Unable to retrieve personalized recommendations: {error_msg}"
        return result
        
    except Exception as e:
        customer_id = tool_context.agent.state.get("customer_id", "unknown")
        session_id = tool_context.agent.state.get("session_id", "unknown")
        return f"Unable to retrieve personalized recommendations: {str(e)}"


def _get_configuration() -> str:
    """
    Retrieve configuration from SSM Parameter Store.
    
    Returns:
        runtime_id: The personalization agent runtime ID
    """
    ssm_client = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
    
    # Get parameter name from environment variable (set by supervisor CDK)
    param_name = os.environ.get('PERSONALIZATION_AGENT_RUNTIME_ID_PARAM')
    if not param_name:
        raise ValueError("PERSONALIZATION_AGENT_RUNTIME_ID_PARAM environment variable not set")
    
    runtime_id_param = ssm_client.get_parameter(Name=param_name)
    runtime_id = runtime_id_param['Parameter']['Value']
    
    return runtime_id



