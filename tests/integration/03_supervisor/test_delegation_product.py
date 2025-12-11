#!/usr/bin/env python3
"""
Supervisor Agent Product Recommendation Delegation Tests

Validates the supervisor agent correctly delegates to the Product Recommendation agent.
"""

import sys
import time
from datetime import datetime

import pytest

from tests.integration.utils import (
    load_config,
    get_jwt_token,
    invoke_agentcore_runtime,
    check_delegation_in_logs,
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


def test_supervisor_delegates_to_product_recommendation(config, jwt_token):
    """Test supervisor delegates product queries to Product Recommendation agent."""
    print("\nTest: Supervisor Delegation to Product Recommendation")
    print("-" * 60)
    
    session_id = f"test-delegation-product-{int(time.time())}"
    start_time = datetime.utcnow()
    
    # Invoke supervisor with product-specific query
    success, status, response = invoke_agentcore_runtime(
        runtime_arn=config['supervisor_runtime_arn'],
        jwt=jwt_token,
        customer_id=config['test_user']['customer_id'],
        session_id=session_id,
        query="Can you recommend some products for me based on my interests?",
        region=config['aws_region'],
        timeout=60
    )
    
    assert success, f"Supervisor invocation failed (HTTP {status})"
    print(f"✓ Supervisor invoked successfully (HTTP {status})")
    
    # Wait for logs to propagate
    print("Waiting for logs to propagate...")
    time.sleep(15)
    
    # Extract log group name from runtime ARN
    runtime_name = config['supervisor_runtime_arn'].split('/')[-1]
    log_group = f"/aws/bedrock-agentcore/runtimes/{runtime_name}-DEFAULT"
    
    # Check logs for delegation evidence
    delegation_found, analysis = check_delegation_in_logs(
        log_group=log_group,
        start_time=start_time,
        region=config['aws_region'],
        session_id=session_id,
        target_runtime_name="product"
    )
    
    assert delegation_found, "Failed to query delegation logs"
    assert analysis, "No delegation analysis returned"
    
    print(f"\n  Delegation Analysis:")
    print(f"    Total log events: {analysis.get('total_events', 0)}")
    print(f"    Tool call found: {analysis.get('tool_call_found', False)}")
    print(f"    Target tool called: {analysis.get('target_tool_called', False)}")
    print(f"    Customer ID found: {analysis.get('customer_id_found', False)}")
    print(f"    Session ID found: {analysis.get('session_id_found', False)}")
    
    # Verify essential delegation requirements
    # Tool call is the critical indicator of delegation
    assert analysis.get('tool_call_found', False), \
        "No tool call to sub-agent found in logs"
    assert analysis.get('target_tool_called', False), \
        "Target tool not called in logs"
    
    print("\n✓ Delegation to Product Recommendation verified")
    print("✓ PASSED")


if __name__ == '__main__':
    # Allow running as standalone script
    sys.exit(pytest.main([__file__, '-v']))
