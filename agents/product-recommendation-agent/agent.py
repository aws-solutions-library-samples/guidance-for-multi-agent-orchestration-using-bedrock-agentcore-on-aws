from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from typing import List, Optional
import os
import json
from system_prompt import PRODUCT_RECOMMENDATION_AGENT_SYSTEM_PROMPT

# Gateway configuration from environment variables
SPONSORED_GATEWAY_ID = os.environ.get('SPONSORED_GATEWAY_ID', 'default-sponsored-gateway-id')
ORGANIC_GATEWAY_ID = os.environ.get('ORGANIC_GATEWAY_ID', 'default-organic-gateway-id')
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
    """
    Process product recommendation request with Gateway tools and memory

    Args:
        payload: {
            "query": str,  # The query from user
            "customer_id": str,
            "session_id": str
        }
        context: RequestContext from AgentCore runtime

    Returns:
        str: Natural language response with product recommendations
    """
    # Use app.logger for logging instead of standalone logger
    app.logger.info("=" * 80)
    app.logger.info("ProductRecommendationAgent starting")
    app.logger.info(f"Environment: SPONSORED_GATEWAY_ID={SPONSORED_GATEWAY_ID}, ORGANIC_GATEWAY_ID={ORGANIC_GATEWAY_ID}")
    app.logger.info(f"Payload received: {json.dumps(payload)}")
    app.logger.info("=" * 80)

    try:
        # Extract parameters from payload
        customer_id = payload.get("customer_id")
        # Support both "query" and "prompt" for backward compatibility
        query = payload.get("query") or payload.get("prompt", "")
        session_id = payload.get("session_id")
        
        app.logger.info(f"Processing request for customer_id={customer_id}, session_id={session_id}")
        app.logger.info(f"Query: {query}")
        
        if not customer_id:
            app.logger.error("Missing customer_id in request")
            return "Error: customer_id is required for product recommendation agent"
        
        if not session_id:
            app.logger.error("Missing session_id in request")
            return "Error: session_id is required for product recommendation agent"
        
        # Get Authorization header from request - following pattern from working agents
        print(f"DEBUG: Request context type: {type(context)}")
        print(f"DEBUG: Request context dir: {dir(context)}")
        print(f"DEBUG: Request context available: {hasattr(context, 'request_headers')}")
        
        if hasattr(context, 'request_headers') and context.request_headers is not None:
            print(f"DEBUG: Available headers: {list(context.request_headers.keys())}")
            auth_header = context.request_headers.get("Authorization", "")
            print(f"DEBUG: Authorization header found: {bool(auth_header)}")
        else:
            auth_header = ""
            print("DEBUG: No request_headers available")
            
        # Try alternative ways to get the token
        if not auth_header and hasattr(context, '__dict__'):
            print(f"DEBUG: Context dict: {context.__dict__}")

        if not auth_header:
            app.logger.warning("No Authorization header found in context. Using empty token for testing.")
            # For testing purposes, continue without auth header
            # In production, this should fail
            access_token = ""
        else:
            # Extract bearer token
            access_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header
            app.logger.info("Authorization token extracted successfully")

        # For testing: if no access token, return a simple response without using Gateway tools
        if not access_token:
            app.logger.warning("Running in test mode without Gateway tools")
            return {
                "sponsored_products": [],
                "organic_products": [],
                "summary": f"Test mode: Received query '{query}' for customer {customer_id}. Gateway tools require authentication.",
                "total_products": 0
            }
        
        # Create MCP clients for both gateways
        sponsored_gateway_url = f"https://{SPONSORED_GATEWAY_ID}.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp"
        organic_gateway_url = f"https://{ORGANIC_GATEWAY_ID}.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp"
        
        app.logger.info(f"Sponsored Gateway URL: {sponsored_gateway_url}")
        app.logger.info(f"Organic Gateway URL: {organic_gateway_url}")
        
        try:
            app.logger.info("Creating MCP clients for gateways...")
            sponsored_mcp_client = MCPClient(lambda: create_streamable_http_transport(sponsored_gateway_url, access_token))
            app.logger.info("Sponsored MCP client created successfully")

            organic_mcp_client = MCPClient(lambda: create_streamable_http_transport(organic_gateway_url, access_token))
            app.logger.info("Organic MCP client created successfully")
        except Exception as e:
            app.logger.error(f"Failed to create MCP clients: {e}", exc_info=True)
            raise Exception(f"MCP client creation failed: {str(e)}")

        # Discover tools from both gateways
        app.logger.info("Discovering tools from gateways...")
        try:
            with sponsored_mcp_client, organic_mcp_client:
                sponsored_tools = get_full_tools_list(sponsored_mcp_client)
                organic_tools = get_full_tools_list(organic_mcp_client)

                # Combine all tools
                tools = sponsored_tools + organic_tools

                app.logger.info(f"Found {len(sponsored_tools)} sponsored tools: {[tool.tool_name for tool in sponsored_tools]}")
                app.logger.info(f"Found {len(organic_tools)} organic tools: {[tool.tool_name for tool in organic_tools]}")
                app.logger.info(f"Total {len(tools)} tools available")

                # Create agent (no memory - stateless product search)
                app.logger.info("Creating agent...")
                agent = Agent(
                    model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
                    system_prompt=PRODUCT_RECOMMENDATION_AGENT_SYSTEM_PROMPT,
                    tools=tools,
                    agent_id="product-recommendation-agent",
                    name="ProductRecommendationAgent"
                )

                # Process query - agent uses tools to gather data
                app.logger.info(f"Processing query: {query}")

                agent_response = agent(query)
                app.logger.info(f"Agent response received: {str(agent_response)[:200]}...")
                app.logger.info("Request processed successfully")

                # Return agent response
                return agent_response
        except Exception as e:
            app.logger.error(f"Error in MCP client operations: {e}", exc_info=True)
            raise Exception(f"MCP operations failed: {str(e)}")

    except Exception as e:
        # Log error with full traceback
        app.logger.error(f"Error processing request: {e}", exc_info=True)
        return f"Unable to generate recommendations: {str(e)}"

if __name__ == "__main__":
    # Start AgentCore app on port 8080
    print("=" * 80)
    print("Starting ProductRecommendationAgent application...")
    print(f"Region: {REGION}")
    print(f"Log Level: {LOG_LEVEL}")
    print(f"Sponsored Gateway ID: {SPONSORED_GATEWAY_ID}")
    print(f"Organic Gateway ID: {ORGANIC_GATEWAY_ID}")
    print("=" * 80)
    app.run()
