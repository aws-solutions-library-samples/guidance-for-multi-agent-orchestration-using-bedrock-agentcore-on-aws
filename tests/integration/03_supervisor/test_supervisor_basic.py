#!/usr/bin/env python3
"""
Supervisor Agent Basic Functionality Tests

Validates the supervisor agent can respond to simple queries.
"""

import sys
import time

import pytest

from tests.integration.utils import (
    load_config,
    get_jwt_token,
    invoke_agentcore_runtime,
    validate_runtime_response,
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


def test_supervisor_simple_query(config, jwt_token):
    """Test supervisor agent responds to simple queries."""
    print("\nTest: Supervisor Simple Query")
    print("-" * 60)
    
    session_id = f"test-supervisor-basic-{int(time.time())}-session"
    
    success, status, response = invoke_agentcore_runtime(
        runtime_arn=config['supervisor_runtime_arn'],
        jwt=jwt_token,
        customer_id=config['test_user']['customer_id'],
        session_id=session_id,
        query="What is the status of my recent orders?",
        region=config['aws_region'],
        timeout=60
    )
    
    assert success, f"Runtime invocation failed (HTTP {status})"
    assert status == 200, f"Expected HTTP 200, got {status}"
    
    # Validate response structure
    response_valid, issues = validate_runtime_response(response)
    assert response_valid, f"Invalid response: {issues[0] if issues else 'Unknown error'}"
    
    print(f"✓ Status: HTTP {status}")
    print("✓ Response is valid")
    print("✓ PASSED")


if __name__ == '__main__':
    # Allow running as standalone script
    sys.exit(pytest.main([__file__, '-v']))
