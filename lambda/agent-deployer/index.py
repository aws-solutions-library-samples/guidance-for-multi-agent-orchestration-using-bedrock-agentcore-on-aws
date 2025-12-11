"""
AgentCore runtime management Lambda function with CloudFormation Custom Resource support
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
    physical_resource_id = event.get('PhysicalResourceId', 'runtime-resource')
    
    try:
        if request_type == 'Create':
            logger.info("Handling CREATE event")
            properties = event.get('ResourceProperties', {})
            runtime_name = properties.get('RuntimeName', 'CustomerSupportRuntime')
            description = properties.get('Description', 'Runtime for customer support assistant')
            role_arn = properties.get('RoleArn')
            container_uri = properties.get('ContainerUri')
            
            if not role_arn or not container_uri:
                raise ValueError("RoleArn and ContainerUri are required properties")
            
            runtime_id, runtime_arn = create_agent_runtime(runtime_name, description, role_arn, container_uri)
            physical_resource_id = runtime_id
            response_data = {
                'RuntimeId': runtime_id,
                'RuntimeArn': runtime_arn,
                'RuntimeName': runtime_name
            }
            
        elif request_type == 'Update':
            logger.info("Handling UPDATE event")
            # For now, we'll just log the update - AgentCore runtime updates are complex
            # and may require recreation rather than in-place updates
            runtime_id = event.get('PhysicalResourceId')
            response_data = {
                'RuntimeId': runtime_id,
                'Message': 'Runtime update not implemented - would require recreation'
            }
            
        elif request_type == 'Delete':
            logger.info("Handling DELETE event")
            runtime_id = event.get('PhysicalResourceId')
            
            if runtime_id and runtime_id != 'runtime-resource':  # Don't delete if it's the default placeholder
                try:
                    delete_agent_runtime(runtime_id)
                    response_data = {
                        'RuntimeId': runtime_id,
                        'Message': 'Runtime deleted successfully'
                    }
                except Exception as e:
                    logger.warning(f"Failed to delete runtime {runtime_id}: {e}")
                    # Don't fail the stack deletion if runtime deletion fails
                    response_data = {
                        'RuntimeId': runtime_id,
                        'Message': f'Runtime deletion failed but continuing: {str(e)}'
                    }
            else:
                logger.info("No runtime to delete")
                response_data = {
                    'Message': 'No runtime to delete'
                }
        
    except Exception as e:
        logger.error(f"Error handling custom resource: {e}")
        response_status = 'FAILED'
        response_data = {
            'Error': str(e)
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
        client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
        
        if action == 'create':
            runtime_name = event.get('runtime_name', 'test_runtime')
            description = event.get('description', 'Test runtime')
            role_arn = event.get('role_arn')
            container_uri = event.get('container_uri')
            
            if not role_arn or not container_uri:
                raise ValueError("role_arn and container_uri are required")
            
            runtime_id, runtime_arn = create_agent_runtime(runtime_name, description, role_arn, container_uri)
            
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'runtime_id': runtime_id,
                    'runtime_arn': runtime_arn
                }
            }
            
        elif action == 'list':
            response = client.list_agent_runtimes()
            
            runtimes = []
            for runtime in response.get('agentRuntimeSummaries', []):
                runtimes.append({
                    'id': runtime.get('agentRuntimeId'),
                    'name': runtime.get('agentRuntimeName'),
                    'status': runtime.get('status'),
                    'arn': runtime.get('agentRuntimeArn'),
                    'created_at': str(runtime.get('createdAt')) if runtime.get('createdAt') else None
                })
            
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'runtimes': runtimes
                }
            }
            
        elif action == 'get':
            runtime_id = event.get('runtime_id')
            if not runtime_id:
                raise ValueError("runtime_id required for get action")
            
            logger.info(f"Getting runtime: {runtime_id}")
            
            response = client.get_agent_runtime(agentRuntimeId=runtime_id)
            runtime = response.get('agentRuntime', {})
            
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'runtime': {
                        'id': runtime.get('agentRuntimeId'),
                        'name': runtime.get('agentRuntimeName'),
                        'status': runtime.get('status'),
                        'arn': runtime.get('agentRuntimeArn'),
                        'description': runtime.get('description'),
                        'created_at': str(runtime.get('createdAt')) if runtime.get('createdAt') else None
                    }
                }
            }
            
        elif action == 'delete':
            runtime_id = event.get('runtime_id')
            if not runtime_id:
                raise ValueError("runtime_id required for delete action")
            
            delete_agent_runtime(runtime_id)
            
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'runtime_id': runtime_id
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

def create_agent_runtime(runtime_name, description, role_arn, container_uri):
    """Create AgentCore runtime"""
    
    client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
    
    logger.info(f"Creating runtime: {runtime_name}")
    
    response = client.create_agent_runtime(
        agentRuntimeName=runtime_name,
        description=description,
        roleArn=role_arn,
        agentRuntimeArtifact={
            'containerConfiguration': {
                'containerUri': container_uri
            }
        },
        networkConfiguration={
            'networkMode': 'PUBLIC'
        }
    )
    
    runtime_id = response['agentRuntimeId']
    runtime_arn = response['agentRuntimeArn']
    logger.info(f"Runtime created: {runtime_id}")
    return runtime_id, runtime_arn

def delete_agent_runtime(runtime_id):
    """Delete AgentCore runtime"""
    
    client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
    
    logger.info(f"Deleting runtime: {runtime_id}")
    client.delete_agent_runtime(agentRuntimeId=runtime_id)
    logger.info(f"Runtime deleted successfully: {runtime_id}")

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