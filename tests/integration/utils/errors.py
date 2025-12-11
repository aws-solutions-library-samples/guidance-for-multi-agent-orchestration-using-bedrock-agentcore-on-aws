"""
Error classes and categories for test utilities.
"""

from enum import Enum
from typing import Any, Dict


class ErrorCategory(Enum):
    """Categories of test errors for troubleshooting."""
    INFRASTRUCTURE = "Infrastructure"
    AUTHENTICATION = "Authentication"
    RUNTIME = "Runtime"
    GATEWAY = "Gateway"
    AGENT = "Agent"
    MEMORY = "Memory"
    KNOWLEDGE_BASE = "KnowledgeBase"


class ValidationError(Exception):
    """Base exception for test errors with categorization."""
    
    # Tell pytest not to collect this as a test class
    __test__ = False
    
    def __init__(self, category: ErrorCategory, message: str, details: Dict[str, Any]):
        self.category = category
        self.message = message
        self.details = details
        super().__init__(message)


# Backward compatibility aliases
TestError = ValidationError
IntegrationTestError = ValidationError
