#!/usr/bin/env python3
"""
CloudWatch logging configuration for AgentCore
"""
import os
import sys
import logging
import boto3
from datetime import datetime

def setup_cloudwatch_logging():
    """
    Configure logging to send directly to CloudWatch Logs
    """
    # Import watchtower here to avoid dependency issues if not installed
    try:
        from watchtower import CloudWatchLogHandler
    except ImportError:
        print("Warning: watchtower not installed, falling back to console logging")
        return logging.getLogger()

    # Configuration
    log_group = os.environ.get('CLOUDWATCH_LOG_GROUP', '/aws/agentcore/product-recommendation-agent')
    log_stream = os.environ.get('CLOUDWATCH_LOG_STREAM', f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    region = os.environ.get('AWS_REGION', 'us-east-1')
    log_level = os.environ.get('LOG_LEVEL', 'INFO')

    # Create CloudWatch client
    cloudwatch_client = boto3.client('logs', region_name=region)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add CloudWatch handler
    try:
        cw_handler = CloudWatchLogHandler(
            log_group=log_group,
            stream_name=log_stream,
            boto3_client=cloudwatch_client,
            create_log_group=False  # Log group should already exist
        )
        cw_handler.setLevel(getattr(logging, log_level))

        # Set formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        cw_handler.setFormatter(formatter)

        root_logger.addHandler(cw_handler)
        print(f"CloudWatch logging configured: {log_group}/{log_stream}")
    except Exception as e:
        print(f"Failed to configure CloudWatch handler: {e}")
        # Fall back to console logging
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level))
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        root_logger.addHandler(console_handler)

    # Also add console handler for immediate feedback
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(console_handler)

    return root_logger