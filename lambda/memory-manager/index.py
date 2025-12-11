"""
AgentCore Memory management Lambda function with CloudFormation Custom Resource support
"""

import json
import logging
import boto3
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """Handler that supports both direct invocation and CloudFormation custom resource events"""
    
    logger.info(f"Event: {json.dumps(event, default=str)}")
    
    # Check if this is a CloudFormation custom resource event
    if 'RequestType' in event and 'ResponseURL' in event:
        return handle_custom_resource(event, context)
    else:
        return handle_direct_invocation(event, context)

def handle_custom_resource(event, context):
    """Handle CloudFormation custom resource events"""
    
    request_type = event['RequestType']
    response_status = 'SUCCESS'
    response_data = {}
    physical_resource_id = event.get('PhysicalResourceId', 'memory-resource')
    
    try:
        if request_type == 'Create':
            logger.info("Handling CREATE event")
            properties = event.get('ResourceProperties', {})
            memory_name = properties.get('MemoryName', 'CustomerSupportMemory')
            description = properties.get('Description', 'Memory for customer support assistant')
            expiry_days = int(properties.get('EventExpiryDays', 30))
            
            memory_id = create_memory(memory_name, description, expiry_days)
            physical_resource_id = memory_id
            response_data = {
                'MemoryId': memory_id,
                'MemoryName': memory_name
            }
            
        elif request_type == 'Update':
            logger.info("Handling UPDATE event")
            properties = event.get('ResourceProperties', {})
            memory_id = event.get('PhysicalResourceId')
            description = properties.get('Description')
            
            if memory_id and description:
                update_memory(memory_id, description)
                response_data = {
                    'MemoryId': memory_id,
                    'Message': 'Memory updated successfully'
                }
            else:
                logger.info("No updates needed")
                response_data = {
                    'MemoryId': memory_id,
                    'Message': 'No updates performed'
                }
            
        elif request_type == 'Delete':
            logger.info("Handling DELETE event")
            memory_id = event.get('PhysicalResourceId')
            
            if memory_id and memory_id != 'memory-resource':  # Don't delete if it's the default placeholder
                try:
                    delete_memory(memory_id)
                    response_data = {
                        'MemoryId': memory_id,
                        'Message': 'Memory deleted successfully'
                    }
                except Exception as e:
                    logger.warning(f"Failed to delete memory {memory_id}: {e}")
                    # Don't fail the stack deletion if memory deletion fails
                    response_data = {
                        'MemoryId': memory_id,
                        'Message': f'Memory deletion failed but continuing: {str(e)}'
                    }
            else:
                logger.info("No memory to delete")
                response_data = {
                    'Message': 'No memory to delete'
                }
        
    except Exception as e:
        logger.error(f"Error handling custom resource: {type(e).__name__}: {e}")
        logger.error(f"Request type: {request_type}")
        logger.error(f"Properties: {json.dumps(event.get('ResourceProperties', {}), default=str)}")
        response_status = 'FAILED'
        response_data = {
            'Error': f"{type(e).__name__}: {str(e)}"
        }
    
    # Send response to CloudFormation
    send_response(event, context, response_status, response_data, physical_resource_id)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': response_status.lower(),
            'data': response_data
        })
    }

def handle_direct_invocation(event, context):
    """Handle direct Lambda invocation (non-CloudFormation)"""
    
    try:
        action = event.get('action', 'create')
        
        if action == 'create':
            memory_name = event.get('memory_name', 'test_memory')
            description = event.get('description', 'Test memory for AgentCore')
            expiry_days = event.get('expiry_days', 30)
            memory_id = create_memory(memory_name, description, expiry_days)
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'memory_id': memory_id,
                    'memory_name': memory_name
                }
            }
            
        elif action == 'list':
            memories = list_memories()
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'memories': memories
                }
            }
            
        elif action == 'update':
            memory_id = event.get('memory_id')
            description = event.get('description')
            if not memory_id:
                raise ValueError("memory_id required for update action")
            
            update_memory(memory_id, description)
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'memory_id': memory_id,
                    'message': 'Memory updated successfully'
                }
            }
            
        elif action == 'delete':
            memory_id = event.get('memory_id')
            if not memory_id:
                raise ValueError("memory_id required for delete action")
            
            delete_memory(memory_id)
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'memory_id': memory_id
                }
            }
            
        else:
            raise ValueError(f"Unknown action: {action}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': {
                'status': 'error',
                'error': str(e)
            }
        }

def send_response(event, context, response_status, response_data, physical_resource_id):
    """Send response to CloudFormation"""
    
    response_url = event['ResponseURL']
    
    response_body = {
        'Status': response_status,
        'Reason': f'See CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': physical_resource_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data
    }
    
    json_response_body = json.dumps(response_body)
    
    logger.info(f"Response body: {json_response_body}")
    
    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }
    
    try:
        http = urllib3.PoolManager()
        response = http.request('PUT', response_url, body=json_response_body, headers=headers)
        logger.info(f"CloudFormation response status: {response.status}")
    except Exception as e:
        logger.error(f"Failed to send response to CloudFormation: {e}")
        raise

def create_memory(memory_name, description='Test memory for AgentCore', expiry_days=30):
    """Create AgentCore Memory using bedrock-agentcore-control client with strategies"""
    
    try:
        logger.info(f"Creating memory: {memory_name} with description: {description}, expiry_days: {expiry_days}")
        logger.info("Creating memory with 3 strategies: semantic, user preference, and summary")
        
        # Use bedrock-agentcore-control client to create memory
        client = boto3.client('bedrock-agentcore-control')
        
        response = client.create_memory(
            name=memory_name,
            description=description,
            eventExpiryDuration=expiry_days,
            memoryStrategies=[
                {
                    'semanticMemoryStrategy': {
                        'name': 'FactExtractor',
                        'namespaces': ['/facts/{actorId}']
                    }
                },
                {
                    'userPreferenceMemoryStrategy': {
                        'name': 'PreferenceLearner',
                        'namespaces': ['/preferences/{actorId}']
                    }
                },
                {
                    'summaryMemoryStrategy': {
                        'name': 'SessionSummarizer',
                        'namespaces': ['/summaries/{actorId}/{sessionId}']
                    }
                }
            ]
        )
        
        memory_id = response['memory']['id']
        strategies_count = len(response.get('memory', {}).get('strategies', []))
        logger.info(f"Memory created successfully: {memory_id}")
        logger.info(f"Strategies configured: {strategies_count}")
        logger.info(f"Memory ARN: {response['memory'].get('arn', 'N/A')}")
        
        return memory_id
        
    except Exception as e:
        logger.error(f"Error creating memory: {type(e).__name__}: {e}")
        raise

def list_memories():
    """List all AgentCore memories"""
    
    try:
        client = boto3.client('bedrock-agentcore-control')
        
        response = client.list_memories()
        
        result = []
        for memory in response.get('memories', []):
            result.append({
                'id': memory.get('id'),
                'name': memory.get('name'),
                'status': memory.get('status'),
                'created_at': str(memory.get('createdAt')) if memory.get('createdAt') else None
            })
        
        logger.info(f"Listed {len(result)} memories")
        return result
        
    except Exception as e:
        logger.error(f"Error listing memories: {e}")
        raise

def update_memory(memory_id, description=None):
    """Update AgentCore memory using bedrock-agentcore-control client"""
    
    try:
        client = boto3.client('bedrock-agentcore-control')
        
        logger.info(f"Updating memory: {memory_id}")
        
        update_params = {}
        if description:
            update_params['description'] = description
        
        if not update_params:
            raise ValueError("No update parameters provided")
        
        response = client.update_memory(
            memoryId=memory_id,
            **update_params
        )
        
        logger.info(f"Memory updated successfully: {memory_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating memory {memory_id}: {e}")
        raise

def delete_memory(memory_id):
    """Delete AgentCore memory"""
    
    try:
        client = boto3.client('bedrock-agentcore-control')
        
        logger.info(f"Deleting memory: {memory_id}")
        client.delete_memory(memoryId=memory_id)
        logger.info(f"Memory deleted successfully: {memory_id}")
        
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id}: {e}")
        raise