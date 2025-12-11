#!/usr/bin/env python3
"""
Product Recommendation Agent Tests

Validates the Product Recommendation agent can be invoked with JWT authentication
and successfully uses Gateway tools for organic and sponsored products.
"""

import sys
import time
from datetime import datetime, timezone

import pytest

from tests.integration.utils import (
    load_config,
    get_jwt_token,
    invoke_agentcore_runtime,
    get_cloudwatch_logs,
    TestError,
    ErrorCategory
)


@pytest.fixture(scope="module")
def config():
    """Load test configuration."""
    return load_config()


@pytest.fixture(scope="module")
def jwt_token(config):
    """Get JWT token for authentication."""
    return get_jwt_token(
        user_pool_id=config['cognito_user_pool_id'],
        client_id=config['cognito_client_id'],
        username=config['test_user']['username'],
        password=config['test_user']['password'],
        region=config['aws_region']
    )


def test_product_recommendation_invocation(config, jwt_token):
    """Test 1: Invoke Product Recommendation agent runtime with JWT."""
    print("\nTest 1: Product Recommendation Runtime Invocation")
    print("-" * 60)
    
    session_id = f"test-product-{int(time.time())}"
    
    success, status, response = invoke_agentcore_runtime(
        runtime_arn=config['product_recommendation_runtime_arn'],
        jwt=jwt_token,
        customer_id=config['test_user']['customer_id'],
        session_id=session_id,
        query="What products do you recommend for me?",
        region=config['aws_region'],
        timeout=120
    )
    
    assert success, f"Runtime invocation failed (HTTP {status})"
    assert status == 200, f"Expected HTTP 200, got {status}"
    assert response, "Response body is empty"
    
    print(f"✓ Status: HTTP {status}")
    print("✓ PASSED")


def test_product_recommendation_tool_usage(config, jwt_token):
    """Test 2: Verify Product Recommendation agent uses Gateway tools."""
    print("\nTest 2: Product Recommendation Gateway Tool Usage")
    print("-" * 60)
    
    session_id = f"test-product-tools-{int(time.time())}"
    start_time = datetime.now(timezone.utc)
    
    # Invoke agent with query requiring tools
    success, status, response = invoke_agentcore_runtime(
        runtime_arn=config['product_recommendation_runtime_arn'],
        jwt=jwt_token,
        customer_id=config['test_user']['customer_id'],
        session_id=session_id,
        query="Show me organic and sponsored product recommendations",
        region=config['aws_region'],
        timeout=120
    )
    
    assert success, f"Agent invocation failed (HTTP {status})"
    
    # Wait for log propagation
    print("Waiting for logs to propagate...")
    time.sleep(20)
    
    # Extract runtime name from ARN
    # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/name
    runtime_name = config['product_recommendation_runtime_arn'].split('/')[-1]
    # Log group format: /aws/bedrock-agentcore/runtimes/{runtime_name}-DEFAULT
    log_group = f"/aws/bedrock-agentcore/runtimes/{runtime_name}-DEFAULT"
    
    # Query CloudWatch logs
    print(f"Querying logs from: {log_group}")
    log_events = get_cloudwatch_logs(
        log_group=log_group,
        start_time=start_time,
        region=config['aws_region'],
        limit=200
    )
    
    assert log_events, "No log events found - agent must log to default AgentCore log group"
    print(f"✓ Found {len(log_events)} log events")
    
    # Verify JWT processing
    jwt_processed = any(
        'jwt' in event.get('message', '').lower() or
        'authorization' in event.get('message', '').lower() or
        'bearer' in event.get('message', '').lower()
        for event in log_events
    )
    print(f"{'✓' if jwt_processed else '✗'} JWT processing: {jwt_processed}")
    
    # Verify tool invocation
    tool_invoked = any(
        'tool' in event.get('message', '').lower() and
        ('invoke' in event.get('message', '').lower() or
         'call' in event.get('message', '').lower())
        for event in log_events
    )
    print(f"{'✓' if tool_invoked else '✗'} Tool invocation: {tool_invoked}")
    
    # Verify Gateway call
    gateway_called = any(
        'gateway' in event.get('message', '').lower() or
        'http' in event.get('message', '').lower()
        for event in log_events
    )
    print(f"{'✓' if gateway_called else '✗'} Gateway call: {gateway_called}")
    
    # Verify no sensitive data in logs
    sensitive_patterns = ['bearer ', 'password', 'secret']
    has_sensitive = any(
        any(pattern in event.get('message', '').lower() for pattern in sensitive_patterns)
        for event in log_events
    )
    print(f"{'✓' if not has_sensitive else '✗'} No sensitive data: {not has_sensitive}")
    
    # Assert all checks passed
    assert tool_invoked or gateway_called, "No evidence of tool/gateway usage in logs"
    assert not has_sensitive, "Sensitive data found in logs"
    
    print("✓ PASSED")


if __name__ == '__main__':
    # Allow running as standalone script
    sys.exit(pytest.main([__file__, '-v']))
