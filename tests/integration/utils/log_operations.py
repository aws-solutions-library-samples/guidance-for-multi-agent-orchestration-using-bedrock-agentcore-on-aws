"""
CloudWatch log query and analysis utilities.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from .errors import ErrorCategory, TestError


def get_cloudwatch_logs(
    log_group: str,
    start_time: datetime,
    region: str = 'us-east-1',
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch recent CloudWatch logs from a log group.
    
    Args:
        log_group: CloudWatch log group name
        start_time: Start time for log query
        region: AWS region (default: us-east-1)
        limit: Maximum number of log events to return
        
    Returns:
        List of log event dictionaries
        
    Raises:
        TestError: If log query fails
    """
    try:
        logs = boto3.client('logs', region_name=region)
        
        # Convert datetime to milliseconds since epoch
        # If naive datetime, treat as UTC (CloudWatch uses UTC)
        if start_time.tzinfo is None:
            start_time_utc = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time_utc = start_time
        
        start_ms = int(start_time_utc.timestamp() * 1000)
        
        # Use filter_log_events with start time
        response = logs.filter_log_events(
            logGroupName=log_group,
            startTime=start_ms,
            limit=limit
        )
        
        return response.get('events', [])
        
    except ClientError as e:
        raise TestError(
            ErrorCategory.INFRASTRUCTURE,
            f"Failed to query CloudWatch logs: {str(e)}",
            {'log_group': log_group, 'error': str(e)}
        )


def check_jwt_processing(log_events: List[Dict[str, Any]]) -> bool:
    """
    Check if JWT was processed in logs.
    
    Args:
        log_events: List of log event dictionaries
        
    Returns:
        True if JWT processing found, False otherwise
    """
    for event in log_events:
        message = event.get('message', '').lower()
        
        # Check for JWT processing indicators (but not the actual token)
        if any(pattern in message for pattern in ['authorization', 'jwt', 'token', 'authenticated']):
            # Make sure actual token not logged
            if 'eyJ' not in event.get('message', ''):
                return True
    
    return False


def check_tool_invocation(log_events: List[Dict[str, Any]], tool_name: str) -> bool:
    """
    Check if tool was invoked in logs.
    
    Args:
        log_events: List of log event dictionaries
        tool_name: Name of the tool to look for
        
    Returns:
        True if tool invocation found, False otherwise
    """
    tool_name_lower = tool_name.lower()
    
    for event in log_events:
        message = event.get('message', '').lower()
        
        # Check for tool invocation patterns
        if tool_name_lower in message and any(pattern in message for pattern in [
            'invoke', 'invocation', 'calling', 'tool', 'function'
        ]):
            return True
    
    return False


def check_gateway_call(log_events: List[Dict[str, Any]]) -> bool:
    """
    Check if Gateway was called in logs.
    
    Args:
        log_events: List of log event dictionaries
        
    Returns:
        True if Gateway call found, False otherwise
    """
    for event in log_events:
        message = event.get('message', '').lower()
        
        # Check for Gateway call patterns
        if 'gateway' in message and any(pattern in message for pattern in [
            'call', 'invoke', 'request', 'http', 'post'
        ]):
            return True
    
    return False


def check_sensitive_data(log_events: List[Dict[str, Any]]) -> bool:
    """
    Check if sensitive data appears in logs.
    
    Args:
        log_events: List of log event dictionaries
        
    Returns:
        True if sensitive data found (BAD), False if no sensitive data (GOOD)
    """
    sensitive_patterns = [
        'eyJ',  # JWT tokens start with this
        'password',
        'secret',
        'api_key',
        'apikey'
    ]
    
    for event in log_events:
        message = event.get('message', '').lower()
        
        # Check for sensitive patterns
        for pattern in sensitive_patterns:
            if pattern in message:
                # Special case: "password" in context like "password_required" is OK
                if pattern == 'password' and 'password_required' in message:
                    continue
                return True
    
    return False
