"""
Product Recommendation Agent Client Tool

Invokes the product recommendation agent runtime for product queries.
Uses JWT authentication with HTTP requests (same pattern as personalization agent).
"""

import os
import boto3
from strands import tool, ToolContext


@tool(context=True)
def product_recommendation_tool(query: str, tool_context: ToolContext) -> str:
    """
    Get product suggestions from catalog with pricing, ratings, and availability. Include customer preferences in query for personalized recommendations.
    
    Args:
        query: The product recommendation query (include customer preferences, categories, or price range for better results)
        
    Returns:
        Response from the product recommendation agent or structured error message
    """
    try:
        # Get customer_id and session_id from agent state
        customer_id = tool_context.agent.state.get("customer_id")
        if not customer_id:
            return "Unable to retrieve product recommendations: Customer ID not available"
        
        
        # Get JWT token from agent state (proper Strands approach)
        jwt_token = tool_context.agent.state.get("jwt_token")
        
        if not jwt_token:
            return "Unable to retrieve product recommendations: Authentication token not available"
        
        # Get session_id from agent state and append agent suffix for unique memory namespace
        base_session_id = tool_context.agent.state.get("session_id")
        if not base_session_id:
            import uuid
            base_session_id = str(uuid.uuid4())
        
        # Append agent identifier for memory isolation
        session_id = f"{base_session_id}-product"
        
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
        
        payload = {
            'query': query,
            'customer_id': customer_id,
            'session_id': session_id,
            'jwt_token': jwt_token  # Pass JWT token in payload as workaround for header pass-through
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            return response.text
        else:
            error_msg = f"Agent returned status {response.status_code}: {response.text}"
            return f"Unable to retrieve product recommendations: {error_msg}"
        
    except Exception as e:
        return f"Unable to retrieve product recommendations: {str(e)}"


def _get_configuration() -> str:
    """
    Retrieve product recommendation agent runtime ID from SSM Parameter Store.
    
    Returns:
        runtime_id: The product recommendation agent runtime ID
    """
    ssm_client = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
    
    # Get parameter name from environment variable (set by supervisor CDK)
    runtime_id_param_name = os.environ.get('PRODUCT_RECOMMENDATION_AGENT_RUNTIME_ID_PARAM')
    if not runtime_id_param_name:
        raise ValueError("PRODUCT_RECOMMENDATION_AGENT_RUNTIME_ID_PARAM environment variable not set")
    
    runtime_id_param = ssm_client.get_parameter(Name=runtime_id_param_name)
    runtime_id = runtime_id_param['Parameter']['Value']
    
    return runtime_id
