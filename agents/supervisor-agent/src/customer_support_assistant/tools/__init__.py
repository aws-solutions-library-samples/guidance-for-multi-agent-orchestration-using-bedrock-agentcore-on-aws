"""
Customer Support Assistant Tools

This module provides tools for the customer support assistant supervisor agent.
All tools follow the Strands SDK @tool decorator pattern.
"""

from .order_management_client import order_management_tool
from .personalization_client import personalization_agent_tool
from .product_recommendation import product_recommendation_tool
from .troubleshooting import troubleshooting_tool

__all__ = [
    "order_management_tool",
    "personalization_agent_tool",
    "product_recommendation_tool",
    "troubleshooting_tool",
]
