"""
Configuration management utilities for tests.
"""

import json
import os
from typing import Any, Dict, List, Tuple


def load_config() -> Dict[str, Any]:
    """
    Load test configuration from test_config.json.
    
    Returns:
        Dictionary containing test configuration
        
    Raises:
        FileNotFoundError: If test_config.json doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    # Look for config in tests/integration directory
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'test_config.json'
    )
    
    # Fallback to deployment_validation directory for backward compatibility
    if not os.path.exists(config_path):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'deployment_validation',
            'test_config.json'
        )
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Run test_00_setup.py first to generate the configuration."
        )
    
    with open(config_path, 'r') as f:
        return json.load(f)


def save_config(config: Dict[str, Any], path: str) -> None:
    """
    Save configuration to JSON file.
    
    Args:
        config: Configuration dictionary to save
        path: Path to save the configuration file
        
    Raises:
        IOError: If file cannot be written
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate configuration has required fields.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        Tuple of (is_valid, missing_fields)
    """
    required_fields = [
        'aws_region',
        'supervisor_runtime_arn',
        'order_mgmt_runtime_arn',
        'personalization_runtime_arn',
        'product_recommendation_runtime_arn',
        'troubleshooting_runtime_arn',
        'order_mgmt_gateway_id',
        'personalization_gateway_id',
        'troubleshooting_gateway_id',
        'cognito_user_pool_id',
        'cognito_client_id',
        'memory_id',
        'kb_id',
        'troubleshooting_kb_id'
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in config or not config[field]:
            missing_fields.append(field)
    
    # Check test_user nested fields
    if 'test_user' in config:
        test_user_fields = ['username', 'password', 'customer_id']
        for field in test_user_fields:
            if field not in config['test_user'] or not config['test_user'][field]:
                missing_fields.append(f'test_user.{field}')
    else:
        missing_fields.append('test_user')
    
    return (len(missing_fields) == 0, missing_fields)
