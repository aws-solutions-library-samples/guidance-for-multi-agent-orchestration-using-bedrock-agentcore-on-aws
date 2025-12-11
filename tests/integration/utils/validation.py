"""
Response validation and delegation verification utilities.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .errors import TestError
from .log_operations import get_cloudwatch_logs


def validate_runtime_response(response_body: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate runtime response structure is valid and contains expected fields.
    
    Args:
        response_body: Response body dictionary
        
    Returns:
        Tuple of (is_valid, issues_list)
    """
    issues = []
    
    # Check if response is empty
    if not response_body:
        issues.append("Response body is empty")
        return (False, issues)
    
    # Check for error field
    if 'error' in response_body:
        issues.append(f"Response contains error: {response_body['error']}")
    
    # Check for common error indicators
    if response_body.get('statusCode') and response_body['statusCode'] >= 400:
        issues.append(f"Response has error status code: {response_body['statusCode']}")
    
    # Check for streaming response (raw_content with SSE data)
    if 'raw_content' in response_body:
        raw_content = response_body['raw_content']
        # Check if it's streaming data (contains "data:" prefix)
        if 'data:' in raw_content:
            # Check for error in streaming data
            if '"error"' in raw_content.lower() and '"error_type"' in raw_content.lower():
                # Extract error message
                try:
                    error_match = re.search(r'"error":\s*"([^"]+)"', raw_content)
                    if error_match:
                        issues.append(f"Streaming response contains error: {error_match.group(1)}")
                except:
                    issues.append("Streaming response contains error")
            # Valid streaming response
            elif 'contentBlockDelta' in raw_content or 'messageStart' in raw_content:
                return (True, [])
    
    # Check for response text or message
    has_response_text = any(key in response_body for key in [
        'response', 'message', 'output', 'text', 'result', 'answer'
    ])
    
    if not has_response_text and not issues:
        issues.append("Response does not contain expected text fields (response/message/output/text/result/answer)")
    
    return (len(issues) == 0, issues)


def check_delegation_in_logs(
    log_group: str,
    start_time: datetime,
    region: str,
    session_id: str,
    target_runtime_name: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check CloudWatch logs for evidence of delegation to sub-agent.
    
    Args:
        log_group: CloudWatch log group name
        start_time: Start time for log query
        region: AWS region
        session_id: Session ID to look for
        target_runtime_name: Name of target runtime (e.g., "order_mgmt", "personalization")
        
    Returns:
        Tuple of (delegation_found, analysis)
    """
    print(f"\n  Querying CloudWatch log group: {log_group}")
    print(f"  Looking for delegation to: {target_runtime_name}")
    
    try:
        # Get logs from CloudWatch
        log_events = get_cloudwatch_logs(
            log_group=log_group,
            start_time=start_time,
            region=region,
            limit=200
        )
        
        if not log_events:
            print(f"  No log events found")
            return (False, {})
        
        print(f"  Found {len(log_events)} log events")
        
        # Analyze logs for delegation evidence
        analysis = {
            'total_events': len(log_events),
            'tool_call_found': False,
            'target_tool_called': False,
            'customer_id_found': False,
            'session_id_found': False,
            'target_runtime_mentioned': False,
            'delegation_logs': []
        }
        
        # Check each log event
        for event in log_events:
            message = event.get('message', '')
            message_lower = message.lower()
            
            # Check for tool calls (Strands agent delegation)
            if 'tool_calls' in message or 'tool_use' in message_lower:
                analysis['tool_call_found'] = True
                analysis['delegation_logs'].append({
                    'timestamp': event.get('timestamp'),
                    'message': message[:300]
                })
                
                # Check if it's calling the target tool
                # Handle both full tool names and partial matches
                # e.g., "order" matches "order_management_tool"
                if f"{target_runtime_name}_tool" in message_lower or \
                   f"{target_runtime_name}_management_tool" in message_lower or \
                   f"{target_runtime_name}_agent_tool" in message_lower or \
                   f"{target_runtime_name}_recommendation_tool" in message_lower:
                    analysis['target_tool_called'] = True
            
            # Check for customer_id
            if 'customer_id' in message_lower or 'test-customer-001' in message:
                analysis['customer_id_found'] = True
            
            # Check for session_id
            if session_id in message:
                analysis['session_id_found'] = True
            
            # Check for target runtime mention
            if target_runtime_name in message_lower:
                analysis['target_runtime_mentioned'] = True
        
        return (True, analysis)
        
    except TestError as e:
        print(f"  Failed to query logs: {e.message}")
        return (False, {})


def check_subagent_logs(
    log_group: str,
    start_time: datetime,
    region: str,
    session_id: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check sub-agent CloudWatch logs for JWT and context propagation.
    
    Args:
        log_group: CloudWatch log group name for sub-agent
        start_time: Start time for log query
        region: AWS region
        session_id: Session ID to look for
        
    Returns:
        Tuple of (logs_found, analysis)
    """
    print(f"\n  Querying sub-agent log group: {log_group}")
    
    try:
        # Get logs from CloudWatch
        log_events = get_cloudwatch_logs(
            log_group=log_group,
            start_time=start_time,
            region=region,
            limit=100
        )
        
        if not log_events:
            print(f"  No log events found in sub-agent logs")
            return (False, {})
        
        print(f"  Found {len(log_events)} log events in sub-agent logs")
        
        # Analyze logs
        analysis = {
            'total_events': len(log_events),
            'jwt_received': False,
            'customer_id_found': False,
            'session_id_found': False,
            'invocation_found': False
        }
        
        for event in log_events:
            message = event.get('message', '')
            message_lower = message.lower()
            
            # Check for JWT processing (but not the actual token)
            if any(pattern in message_lower for pattern in ['authorization', 'jwt', 'token', 'authenticated']):
                if 'eyJ' not in message:  # Make sure actual token not logged
                    analysis['jwt_received'] = True
            
            # Check for customer_id
            if 'customer_id' in message_lower or 'test-customer-001' in message:
                analysis['customer_id_found'] = True
            
            # Check for session_id
            if session_id in message:
                analysis['session_id_found'] = True
            
            # Check for invocation
            if any(pattern in message_lower for pattern in ['invoked', 'invocation', 'request', 'processing']):
                analysis['invocation_found'] = True
        
        return (True, analysis)
        
    except TestError as e:
        print(f"  Failed to query sub-agent logs: {e.message}")
        return (False, {})
