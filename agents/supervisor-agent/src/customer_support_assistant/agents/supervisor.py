#!/usr/bin/env python3
"""
Supervisor Agent for Customer Support Assistant
"""

import uuid
import sys
import traceback
import os
import json
import boto3
from typing import Dict, Any, Optional
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Initialize the AgentCore app
app = BedrockAgentCoreApp()

# Import Strands
from strands import Agent
from strands.hooks import HookProvider, BeforeToolCallEvent, AfterToolCallEvent

# Try to import memory session manager (optional)
try:
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
    from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
    MEMORY_SESSION_MANAGER_AVAILABLE = True
except ImportError:
    MEMORY_SESSION_MANAGER_AVAILABLE = False

# Import tools
from customer_support_assistant.tools import (
    order_management_tool,
    product_recommendation_tool,
    personalization_agent_tool,
    troubleshooting_tool
)

# Import config
from customer_support_assistant.utils.config import config_manager


class ToolLoggingHook(HookProvider):
    """Hook to log tool invocations"""
    
    def on_before_tool_call(self, event: BeforeToolCallEvent):
        """Log before tool is called"""
        app.logger.info(f"Calling tool: {event.tool_name} with input: {str(event.tool_input)[:200]}")
    
    def on_after_tool_call(self, event: AfterToolCallEvent):
        """Log after tool completes"""
        result_preview = str(event.tool_result)[:200] if event.tool_result else "None"
        app.logger.info(f"Tool {event.tool_name} completed - result preview: {result_preview}")


def _extract_user_info_from_token(context) -> Optional[dict]:
    """Extract user info from Cognito access token."""
    try:
        if not hasattr(context, 'request_headers'):
            return None
            
        auth_header = context.request_headers.get('Authorization')
        if not auth_header:
            return None
        
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header
        
        # Use Cognito API to validate token and get user info
        cognito_client = boto3.client('cognito-idp', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        
        try:
            response = cognito_client.get_user(AccessToken=token)
            user_sub = response['Username']
            
            # Extract customer info from user attributes
            user_info = {'user_sub': user_sub}
            for attr in response.get('UserAttributes', []):
                if attr['Name'] == 'custom:customer_id':
                    user_info['customer_id'] = attr['Value']
                elif attr['Name'] == 'given_name':
                    user_info['given_name'] = attr['Value']
                elif attr['Name'] == 'family_name':
                    user_info['family_name'] = attr['Value']
            
            return user_info
        except Exception as cognito_error:
            print(f"Cognito get_user failed: {cognito_error}")
            return None
            
    except Exception as e:
        return None


def _get_customer_info_from_cognito(user_sub: str) -> Optional[dict]:
    """Get customer info from Cognito user attributes."""
    try:
        user_pool_id = os.environ.get('USER_POOL_ID')
        if not user_pool_id:
            return None
        
        region = os.environ.get('AWS_REGION', 'us-east-1')
        cognito = boto3.client('cognito-idp', region_name=region)
        
        response = cognito.admin_get_user(
            UserPoolId=user_pool_id,
            Username=user_sub
        )
        
        # Extract attributes
        customer_info = {}
        for attr in response.get('UserAttributes', []):
            if attr['Name'] == 'custom:customer_id':
                customer_info['customer_id'] = attr['Value']
            elif attr['Name'] == 'given_name':
                customer_info['given_name'] = attr['Value']
            elif attr['Name'] == 'family_name':
                customer_info['family_name'] = attr['Value']
        
        if 'customer_id' in customer_info:
            return customer_info
        
        return None
        
    except Exception as e:
        return None


@app.entrypoint
async def invoke(payload, context):
    """Main entry point for the supervisor agent."""
    try:
        # Extract customer query
        if "prompt" not in payload:
            error_msg = f"Missing 'prompt' in payload. Keys: {list(payload.keys())}"
            raise ValueError(error_msg)
        
        customer_query = payload["prompt"]
        
        # Get user info from Cognito access token
        user_info = _extract_user_info_from_token(context)
        
        customer_id = None
        customer_name = None
        if user_info:
            customer_id = user_info.get('customer_id')
            # Build full name if available
            given_name = user_info.get('given_name')
            family_name = user_info.get('family_name')
            if given_name and family_name:
                customer_name = f"{given_name} {family_name}"
            elif given_name:
                customer_name = given_name
        
        # Get JWT token for passing to agent state
        jwt_token = None
        if hasattr(context, 'request_headers') and context.request_headers:
            jwt_token = context.request_headers.get('Authorization')
        
        # Fallback to context.user_id
        if not customer_id and hasattr(context, 'user_id'):
            customer_id = context.user_id
        
        # For local testing, use a default customer_id
        if not customer_id:
            customer_id = "test-customer-local"
        
        # Get memory ID
        memory_id = config_manager.get_memory_id()
        
        # Get session ID - check header first, then context, then generate
        session_id = None
        if hasattr(context, 'request_headers') and context.request_headers:
            session_id = context.request_headers.get('X-Amzn-Bedrock-AgentCore-Runtime-Session-Id')
        
        if not session_id:
            session_id = context.session_id if hasattr(context, 'session_id') else str(uuid.uuid4())
        
        # Create supervisor agent
        # Build tools list
        tools_list = [
            order_management_tool,
            product_recommendation_tool, 
            personalization_agent_tool,
            troubleshooting_tool
        ]
        
        # Create memory session manager if available
        session_manager = None
        if MEMORY_SESSION_MANAGER_AVAILABLE:
            try:
                memory_config = AgentCoreMemoryConfig(
                    memory_id=memory_id,
                    session_id=session_id,
                    actor_id=customer_id,
                    retrieval_config={
                        "/preferences/{actorId}": RetrievalConfig(
                            top_k=5,
                            relevance_score=0.7
                        ),
                        "/facts/{actorId}": RetrievalConfig(
                            top_k=10,
                            relevance_score=0.3
                        )
                    }
                )
                session_manager = AgentCoreMemorySessionManager(
                    agentcore_memory_config=memory_config,
                    region_name=os.environ.get('AWS_REGION', 'us-east-1')
                )
                app.logger.info(f"Memory session manager created: memory_id={memory_id}, actor_id={customer_id}, session_id={session_id}")
            except Exception as e:
                app.logger.error(f"Failed to create memory session manager: {e}", exc_info=True)
        
        supervisor = Agent(
            model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            tools=tools_list,
            system_prompt=_get_system_prompt(customer_id, customer_name),
            session_manager=session_manager,
            hooks=[ToolLoggingHook()]
        )
        
        # Store session_id, customer_id, and customer_name in agent state for tools to access
        supervisor.state.set("session_id", session_id)
        supervisor.state.set("customer_id", customer_id)
        supervisor.state.set("jwt_token", jwt_token)
        if customer_name:
            supervisor.state.set("customer_name", customer_name)
        
        app.logger.info(f"Supervisor agent starting - customer_id={customer_id}, session_id={session_id}, query_length={len(customer_query)}")
        
        # Process query with streaming
        stream = supervisor.stream_async(customer_query)
        
        # Stream all events to client
        async for event in stream:
            yield event
            
    except Exception as e:
        raise


def _get_system_prompt(customer_id: str, customer_name: str = None) -> str:
    """Generate system prompt for the supervisor agent.
    
    Args:
        customer_id: Customer identifier
        customer_name: Customer's full name (optional)
        
    Returns:
        System prompt for the supervisor agent
    """
    customer_greeting = f"{customer_name} (customer ID: {customer_id})" if customer_name else f"customer {customer_id}"
    
    return f"""You are a customer support supervisor agent helping {customer_greeting}. 
You coordinate with specialized agents to provide comprehensive customer support.

Your role is to:
1. Understand the customer's needs and intent
2. Use the appropriate specialized agent tools to help the customer
3. Coordinate between multiple agents when needed
4. Provide clear, helpful responses

Available specialized agents:
- order_management: Query order status, shipping tracking, return status, and inventory availability
- product_recommendation: Provide product suggestions and catalog assistance  
- personalization: Deliver personalized experiences based on customer data
- troubleshooting: Query technical documentation, troubleshooting guides, and FAQs

Privacy Guidelines:
- You may mention loyalty tier information (e.g., "Gold member") when relevant to benefits or offers
- Do NOT mention or reference demographic data, browsing history, or other collected customer information in your responses
- Use personalization insights to inform recommendations, but keep the data itself private

Analyze the customer's request and use the most appropriate tool(s) to help them. You can use multiple tools if needed to provide comprehensive support."""


if __name__ == "__main__":
    app.run()
