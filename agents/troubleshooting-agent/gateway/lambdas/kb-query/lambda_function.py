import json
import boto3
import os
from typing import Dict, Any, List

# Initialize Bedrock Agent Runtime client
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

def query_knowledge_base(query: str, max_results: int = 5) -> List[Dict]:
    """Query Bedrock Knowledge Base using retrieve API.
    
    Args:
        query: The search query text
        max_results: Maximum number of results to return (default: 5)
        
    Returns:
        List of knowledge base results with content and metadata
    """
    knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
    if not knowledge_base_id:
        raise ValueError('KNOWLEDGE_BASE_ID environment variable not set')
    
    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={
                'text': query
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        )
        
        results = []
        for item in response.get('retrievalResults', []):
            results.append({
                'content': item.get('content', {}).get('text', ''),
                'score': item.get('score', 0.0),
                'metadata': item.get('metadata', {})
            })
        
        return results
        
    except Exception as e:
        raise Exception(f"Error querying knowledge base: {str(e)}")

def search_troubleshooting(product_name: str, issue_type: str) -> str:
    """Search for specific product troubleshooting guides.
    
    Args:
        product_name: Name of the product (e.g., 'headphones', 'smartwatch')
        issue_type: Type of issue (e.g., 'bluetooth', 'battery', 'charging')
        
    Returns:
        Formatted troubleshooting guidance as a string
    """
    # Construct a specific query for troubleshooting
    query = f"{product_name} {issue_type} troubleshooting"
    
    try:
        results = query_knowledge_base(query, max_results=3)
        
        if not results:
            return f"No troubleshooting information found for {product_name} {issue_type} issues."
        
        # Format results into readable troubleshooting steps
        output = f"Troubleshooting Guide for {product_name.title()} - {issue_type.title()} Issues:\n\n"
        
        for i, result in enumerate(results, 1):
            output += f"Solution {i} (Confidence: {result['score']:.2f}):\n"
            output += f"{result['content']}\n\n"
        
        return output.strip()
        
    except Exception as e:
        return f"Error searching troubleshooting information: {str(e)}"

def get_faq(product_name: str) -> str:
    """Retrieve FAQ information for a product.
    
    Args:
        product_name: Name of the product
        
    Returns:
        Formatted FAQ information as a string
    """
    # Construct FAQ-specific query
    query = f"{product_name} FAQ frequently asked questions"
    
    try:
        results = query_knowledge_base(query, max_results=5)
        
        if not results:
            return f"No FAQ information found for {product_name}."
        
        # Format results as FAQ entries
        output = f"Frequently Asked Questions for {product_name.title()}:\n\n"
        
        for i, result in enumerate(results, 1):
            output += f"FAQ {i}:\n"
            output += f"{result['content']}\n\n"
        
        return output.strip()
        
    except Exception as e:
        return f"Error retrieving FAQ information: {str(e)}"

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Lambda handler for knowledge base query tools.
    
    Routes requests to appropriate tool functions based on bedrockAgentCoreToolName.
    Handles tool name prefix stripping (e.g., "kb-query___search_troubleshooting").
    """
    try:
        # Get tool name from AgentCore Gateway context and strip prefix
        full_tool_name = context.client_context.custom.get('bedrockAgentCoreToolName')
        if not full_tool_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No tool name provided in context'})
            }
        
        # Strip the prefix (e.g., "kb-query___search_troubleshooting" -> "search_troubleshooting")
        tool_name = full_tool_name.split('___')[-1] if '___' in full_tool_name else full_tool_name
        
        # Route to appropriate tool based on tool name
        if tool_name == 'query_knowledge_base':
            query = event.get('query')
            if not query:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'query parameter is required'})
                }
            
            max_results = event.get('max_results', 5)
            result = query_knowledge_base(query, max_results)
            
        elif tool_name == 'search_troubleshooting':
            product_name = event.get('product_name')
            issue_type = event.get('issue_type')
            
            if not product_name or not issue_type:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'product_name and issue_type are required'})
                }
            
            result = search_troubleshooting(product_name, issue_type)
            
        elif tool_name == 'get_faq':
            product_name = event.get('product_name')
            
            if not product_name:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'product_name is required'})
                }
            
            result = get_faq(product_name)
            
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
