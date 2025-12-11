import json
import boto3
import logging
import urllib3
import time

"""
CDK Custom Resource Lifecycle Patterns (DO NOT BREAK):

CREATE: 
- Returns gateway_id as PhysicalResourceId
- Must include TargetId in data for future operations
- Pattern: send_response(event, "SUCCESS", physical_resource_id=gateway_id, data={'GatewayId': gateway_id, 'TargetId': target_id})

UPDATE:
- Uses PhysicalResourceId from event (gateway_id from CREATE)
- Same PhysicalResourceId = update, different = replacement
- Pattern: send_response(event, "SUCCESS", physical_resource_id=gateway_id, data={'GatewayId': gateway_id})

DELETE:
- Uses PhysicalResourceId from event for cleanup
- Always return SUCCESS to avoid stack deletion issues
- Pattern: send_response(event, "SUCCESS", physical_resource_id=event.get('PhysicalResourceId'))

Required Response Fields: Status, PhysicalResourceId, StackId, RequestId, LogicalResourceId
Optional: Reason (for failures), Data (for Fn::GetAtt)
"""

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """CDK Custom Resource handler for AgentCore Gateway operations."""
    
    logger.info(f"Lambda handler started - RequestType: {event.get('RequestType', 'UNKNOWN')}")
    logger.info(f"Event keys: {list(event.keys())}")
    
    try:
        request_type = event['RequestType']
        properties = event['ResourceProperties']
        
        logger.info(f"Processing {request_type} request")
        
        client = boto3.client('bedrock-agentcore-control')
        
        if request_type == 'Create':
            return handle_create(client, properties, event)
        elif request_type == 'Update':
            return handle_update(client, properties, event)
        elif request_type == 'Delete':
            return handle_delete(client, properties, event)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return send_response(event, "FAILED", str(e))

def handle_create(client, properties, event):
    """Create Gateway and configure multiple target Lambdas."""
    
    logger.info(f"Received properties: {json.dumps(properties, indent=2)}")
    
    gateway_name = properties['GatewayName']
    logger.info(f"Starting CREATE operation for gateway: {gateway_name}")
    
    # Create new gateway - let AWS API fail if it already exists
    try:
        logger.info("Creating new gateway...")
        gateway_response = client.create_gateway(
            name=gateway_name,
            description=properties.get('GatewayDescription', 'Personalization Agent Gateway'),
            roleArn=properties['GatewayRoleArn'],
            protocolType='MCP',
            authorizerType='CUSTOM_JWT',
            authorizerConfiguration={
                'customJWTAuthorizer': {
                    'allowedClients': [properties['CognitoClientId']],
                    'discoveryUrl': properties['CognitoDiscoveryUrl']
                }
            }
        )
        gateway_id = gateway_response['gatewayId']
        logger.info(f"Created new gateway: {gateway_id}")
        
        # Poll for gateway to be READY
        logger.info("Waiting for gateway to be READY...")
        max_attempts = 30
        for attempt in range(max_attempts):
            gateway_status = client.get_gateway(gatewayIdentifier=gateway_id)
            status = gateway_status['status']
            logger.info(f"Gateway status: {status} (attempt {attempt + 1}/{max_attempts})")
            if status == 'READY':
                break
            if status == 'FAILED':
                raise Exception(f"Gateway creation failed")
            time.sleep(2)
        else:
            raise Exception(f"Gateway did not become READY after {max_attempts * 2} seconds")
        logger.info("Gateway is READY")
            
    except Exception as e:
        logger.error(f"Error creating gateway: {e}")
        raise e
    
    # Create targets
    if 'Targets' in properties:
        targets = json.loads(properties['Targets'])
        logger.info(f"Creating {len(targets)} targets")
        
        for i, target in enumerate(targets):
            target_name = target['name']
            logger.info(f"Creating target {i+1}/{len(targets)}: {target_name}")
            
            target_response = client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                targetConfiguration={
                    'mcp': {
                        'lambda': {
                            'lambdaArn': target['lambdaArn'],
                            'toolSchema': {
                                'inlinePayload': json.loads(target['toolSchema'])
                            }
                        }
                    }
                },
                credentialProviderConfigurations=[{
                    'credentialProviderType': 'GATEWAY_IAM_ROLE'
                }]
            )
            logger.info(f"Created target: {target_name} (ID: {target_response['targetId']})")
    else:
        # Legacy single target support
        target_name = properties['TargetName']
        logger.info(f"Creating single target: {target_name}")
        
        target_response = client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=target_name,
            targetConfiguration={
                'mcp': {
                    'lambda': {
                        'lambdaArn': properties['LambdaArn'],
                        'toolSchema': {
                            'inlinePayload': json.loads(properties['ToolSchema'])
                        }
                    }
                }
            },
            credentialProviderConfigurations=[{
                'credentialProviderType': 'GATEWAY_IAM_ROLE'
            }]
        )
        logger.info(f"Created single target: {target_name}")
    
    logger.info(f"CREATE operation completed for gateway: {gateway_id}")
    return send_response(event, "SUCCESS", physical_resource_id=gateway_id, data={
        'GatewayId': gateway_id,
        'TargetId': target_response['targetId'] if 'target_response' in locals() else 'existing'
    })

def handle_update(client, properties, event):
    """Update Gateway and target configuration."""
    
    # DEBUG: Log all received properties
    logger.info(f"UPDATE - Received properties: {json.dumps(properties, indent=2)}")
    logger.info(f"UPDATE - Properties keys: {list(properties.keys())}")
    
    # Get gateway_id from PhysicalResourceId
    gateway_id = event['PhysicalResourceId']
    logger.info(f"UPDATE - Processing gateway: {gateway_id}")
    
    # Update gateway properties
    logger.info("UPDATE - Updating gateway properties...")
    client.update_gateway(
        gatewayIdentifier=gateway_id,
        description=properties.get('GatewayDescription', 'Personalization Agent Gateway'),
        roleArn=properties['GatewayRoleArn'],
        authorizerConfiguration={
            'customJWTAuthorizer': {
                'allowedClients': [properties['CognitoClientId']],
                'discoveryUrl': properties['CognitoDiscoveryUrl']
            }
        }
    )
    logger.info("UPDATE - Gateway properties updated successfully")
    
    # Get existing targets
    existing_targets = {}
    try:
        logger.info(f"UPDATE - Listing existing targets for gateway: {gateway_id}")
        targets_response = client.list_gateway_targets(gatewayIdentifier=gateway_id)
        for target in targets_response.get('items', []):
            existing_targets[target['name']] = target['targetId']
            logger.info(f"UPDATE - Existing target: {target['name']} (ID: {target['targetId']})")
    except Exception as e:
        logger.warning(f"UPDATE - Could not list existing targets: {e}")
    
    # Process targets same as CREATE
    if 'Targets' in properties:
        targets = json.loads(properties['Targets'])
        logger.info(f"UPDATE - Processing {len(targets)} targets from properties")
        
        for i, target in enumerate(targets):
            target_name = target['name']
            logger.info(f"UPDATE - Processing target {i+1}/{len(targets)}: {target_name}")
            
            if target_name in existing_targets:
                logger.info(f"UPDATE - Target {target_name} already exists, skipping")
                continue
            
            try:
                target_response = client.create_gateway_target(
                    gatewayIdentifier=gateway_id,
                    name=target_name,
                    targetConfiguration={
                        'mcp': {
                            'lambda': {
                                'lambdaArn': target['lambdaArn'],
                                'toolSchema': {
                                    'inlinePayload': json.loads(target['toolSchema'])
                                }
                            }
                        }
                    },
                    credentialProviderConfigurations=[{
                        'credentialProviderType': 'GATEWAY_IAM_ROLE'
                    }]
                )
                logger.info(f"UPDATE - Created target {target_name}: {target_response['targetId']}")
            except Exception as e:
                if 'ConflictException' in str(e):
                    logger.info(f"UPDATE - Target {target_name} already exists, skipping")
                else:
                    logger.error(f"UPDATE - Error creating target {target_name}: {e}")
                    raise e
    
    logger.info(f"UPDATE - Operation completed for gateway: {gateway_id}")
    return send_response(event, "SUCCESS", physical_resource_id=gateway_id, data={
        'GatewayId': gateway_id
    })

def handle_delete(client, properties, event):
    """Delete Gateway targets and Gateway."""
    
    gateway_id = event.get('PhysicalResourceId')
    if not gateway_id:
        logger.warning("No PhysicalResourceId provided for delete")
        return send_response(event, "SUCCESS", physical_resource_id=event.get('LogicalResourceId'))
    
    logger.info(f"DELETE - Deleting gateway: {gateway_id}")
    
    # Delete all targets first
    try:
        targets_response = client.list_gateway_targets(gatewayIdentifier=gateway_id)
        targets = targets_response.get('items', [])
        logger.info(f"DELETE - Found {len(targets)} targets to delete")
        
        for target in targets:
            client.delete_gateway_target(
                gatewayIdentifier=gateway_id, 
                targetId=target['targetId']
            )
            logger.info(f"DELETE - Deleted target: {target['targetId']}")
        
        # Wait for all targets to be fully deleted (DeleteGatewayTarget is async - HTTP 202)
        if targets:
            logger.info("DELETE - Waiting for targets to be fully deleted...")
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(2)
                try:
                    remaining_targets = client.list_gateway_targets(gatewayIdentifier=gateway_id)
                    if not remaining_targets.get('items', []):
                        logger.info("DELETE - All targets deleted successfully")
                        break
                    logger.info(f"DELETE - Attempt {attempt + 1}: {len(remaining_targets.get('items', []))} targets remaining")
                except client.exceptions.ResourceNotFoundException:
                    logger.info("DELETE - Gateway not found, targets already deleted")
                    break
            else:
                logger.warning("DELETE - Timeout waiting for targets to delete, proceeding anyway")
            
    except client.exceptions.ResourceNotFoundException:
        logger.info(f"DELETE - Gateway {gateway_id} not found, already deleted")
        return send_response(event, "SUCCESS", physical_resource_id=gateway_id)
    except Exception as e:
        logger.error(f"DELETE - Failed to delete targets: {str(e)}")
        return send_response(event, "FAILED", reason=f"Failed to delete targets: {str(e)}", physical_resource_id=gateway_id)
    
    # Delete the gateway
    try:
        delete_response = client.delete_gateway(gatewayIdentifier=gateway_id)
        logger.info(f"DELETE - Initiated gateway deletion: {gateway_id}")
        
        # Poll for gateway to be fully deleted
        logger.info("DELETE - Waiting for gateway deletion to complete...")
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                gateway_status = client.get_gateway(gatewayIdentifier=gateway_id)
                status = gateway_status['status']
                logger.info(f"DELETE - Gateway status: {status} (attempt {attempt + 1}/{max_attempts})")
                if status == 'FAILED':
                    raise Exception(f"Gateway deletion failed")
                time.sleep(2)
            except client.exceptions.ResourceNotFoundException:
                logger.info("DELETE - Gateway successfully deleted")
                return send_response(event, "SUCCESS", physical_resource_id=gateway_id)
        else:
            raise Exception(f"Gateway deletion did not complete after {max_attempts * 2} seconds")
            
    except client.exceptions.ResourceNotFoundException:
        logger.info(f"DELETE - Gateway {gateway_id} not found, already deleted")
        return send_response(event, "SUCCESS", physical_resource_id=gateway_id)
    except Exception as e:
        logger.error(f"DELETE - Failed to delete gateway: {str(e)}")
        return send_response(event, "FAILED", reason=f"Failed to delete gateway: {str(e)}", physical_resource_id=gateway_id)

def send_response(event, status, reason="", physical_resource_id=None, data=None):
    """Send HTTP response to CloudFormation ResponseURL."""
    
    # Use provided physical_resource_id or fall back to existing logic
    if physical_resource_id:
        resource_id = physical_resource_id
    else:
        resource_id = event.get('PhysicalResourceId', event.get('LogicalResourceId'))
    
    response_body = {
        'Status': status,
        'Reason': reason,
        'PhysicalResourceId': resource_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data or {}
    }
    
    logger.info(f"Sending response: {json.dumps(response_body)}")
    
    http = urllib3.PoolManager()
    response = http.request(
        'PUT',
        event['ResponseURL'],
        body=json.dumps(response_body),
        headers={'Content-Type': 'application/json'}
    )
    
    logger.info(f"Response status: {response.status}")
    return response_body
