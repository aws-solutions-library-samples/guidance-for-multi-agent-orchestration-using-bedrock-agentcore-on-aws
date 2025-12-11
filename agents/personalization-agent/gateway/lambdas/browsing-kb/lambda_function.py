import json
import boto3
import os
from typing import Dict, Any, List

# Knowledge Base configuration - should be set via environment variables
# Updated to trigger custom resource update
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', 'PersonalizationKB-dev')

def query_knowledge_base(query: str, customer_id: str, max_results: int = 5) -> List[Dict]:
    """Query Bedrock Knowledge Base with customer_id metadata filter."""
    try:
        client = boto3.client('bedrock-agent-runtime')
        
        response = client.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results,
                    'filter': {
                        'equals': {
                            'key': 'customer_id',
                            'value': customer_id.upper()
                        }
                    }
                }
            }
        )
        
        return response.get('retrievalResults', [])
    except Exception as e:
        print(f"Knowledge Base query error: {str(e)}")
        return []

def get_browsing_behavior(customer_id: str, limit: int = 5) -> str:
    """Get customer browsing behavior from Knowledge Base."""
    
    # Query Knowledge Base for customer browsing data with metadata filter
    query = f"browsing session product viewed actions"
    results = query_knowledge_base(query, customer_id, limit)
    
    if not results:
        return f"No browsing behavior found for customer {customer_id}"
    
    behavior_text = f"Browsing Behavior for {customer_id} (last {len(results)} sessions):\n"
    
    for i, result in enumerate(results, 1):
        content = result.get('content', {}).get('text', 'No content available')
        score = result.get('score', 0)
        
        # Extract key information from the content
        behavior_text += f"{i}. {content[:200]}{'...' if len(content) > 200 else ''}\n"
        behavior_text += f"   Relevance Score: {score:.3f}\n\n"
    
    return behavior_text.strip()

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Lambda handler for browsing Knowledge Base tools."""
    try:
        # REQUIRED: Get tool name from AgentCore context and strip prefix
        full_tool_name = context.client_context.custom.get('bedrockAgentCoreToolName')
        if not full_tool_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No tool name provided in context'})
            }
        
        # REQUIRED: Strip the prefix (e.g., "browsing-kb___get_browsing_behavior" -> "get_browsing_behavior")
        tool_name = full_tool_name.split('___')[-1] if '___' in full_tool_name else full_tool_name
        
        # Extract parameters from event
        customer_id = event.get('customer_id')
        if not customer_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'customer_id is required'})
            }
        
        # Route to appropriate tool
        if tool_name == 'get_browsing_behavior':
            limit = event.get('limit', 5)
            result = get_browsing_behavior(customer_id, limit)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown tool: {tool_name} (full: {full_tool_name})'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({'result': result})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
