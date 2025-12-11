from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from mcp.client.streamable_http import streamablehttp_client
import os
from system_prompt import PERSONALIZATION_AGENT_SYSTEM_PROMPT

# Gateway configuration from environment variables
GATEWAY_ID = os.environ.get('GATEWAY_ID', 'default-gateway-id')
MEMORY_ID = os.environ.get('MEMORY_ID', 'default-memory-id')
REGION = os.environ.get('AWS_REGION', 'us-east-1')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

def create_streamable_http_transport(mcp_url: str, access_token: str):
    """Create transport for AgentCore Gateway with authentication"""
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})

def get_full_tools_list(client):
    """List tools with support for pagination"""
    more_tools = True
    tools = []
    pagination_token = None
    while more_tools:
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(tmp_tools)
        if tmp_tools.pagination_token is None:
            more_tools = False
        else:
            more_tools = True 
            pagination_token = tmp_tools.pagination_token
    return tools

# Initialize the AgentCore app
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload, context: RequestContext):
    """Process personalization request with Gateway tools and STM for session caching"""
    app.logger.info("PersonalizationAgent starting with Session Manager (STM only)")
    
    customer_id = payload.get("customer_id")
    query = payload.get("query", "")
    session_id = payload.get("session_id")
    
    if not session_id:
        return "Error: session_id is required for personalization agent"
    
    if not customer_id:
        return "Error: customer_id is required for personalization agent"
    
    # Get Authorization header from request
    app.logger.info(f"Request context available: {hasattr(context, 'request_headers')}")
    if hasattr(context, 'request_headers') and context.request_headers is not None:
        app.logger.info(f"Available headers: {list(context.request_headers.keys())}")
        auth_header = context.request_headers.get("Authorization", "")
        app.logger.info(f"Authorization header found: {bool(auth_header)}")
    else:
        auth_header = ""
        app.logger.info("No request_headers available on context")
    
    if not auth_header:
        app.logger.error("No Authorization header found - cannot authenticate with Gateway")
        return "Error: No Authorization header found. Cannot authenticate with Gateway."
    
    # Extract bearer token
    access_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header
    
    # Configure Session Manager with STM only (no LTM strategies)
    memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id,
        actor_id=customer_id
        # No retrieval_config = STM only, no LTM retrieval
    )
    
    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=memory_config,
        region_name=REGION
    )
    
    # Create MCP client for Gateway
    gateway_url = f"https://{GATEWAY_ID}.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp"
    mcp_client = MCPClient(lambda: create_streamable_http_transport(gateway_url, access_token))
    
    with mcp_client:
        tools = get_full_tools_list(mcp_client)
        app.logger.info(f"Found {len(tools)} tools: {[tool.tool_name for tool in tools]}")
        
        # Create agent with session manager for conversation caching
        agent = Agent(
            model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
            tools=tools,
            system_prompt=PERSONALIZATION_AGENT_SYSTEM_PROMPT,
            agent_id="personalization-agent",
            name="PersonalizationAgent",
            session_manager=session_manager
        )
        
        # Process request - agent gathers data and provides natural language response
        # Session manager handles conversation persistence automatically
        agent_response = agent(query)
        
        # Return natural language response (supervisor doesn't need structured data)
        return str(agent_response)

if __name__ == "__main__":
    # Start AgentCore app on port 8080
    app.run()
