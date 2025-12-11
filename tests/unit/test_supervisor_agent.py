"""Unit tests for supervisor agent."""

import pytest
from unittest.mock import patch, MagicMock
from src.customer_support_assistant.agents.supervisor import supervisor_agent_handler


class TestSupervisorAgent:
    """Test cases for supervisor agent functionality."""
    
    @patch('src.customer_support_assistant.agents.supervisor.config_manager')
    @patch('src.customer_support_assistant.agents.supervisor.AgentCoreMemoryToolProvider')
    @patch('src.customer_support_assistant.agents.supervisor.Agent')
    def test_supervisor_agent_handler_success(self, mock_agent, mock_memory_provider, mock_config):
        """Test successful supervisor agent execution."""
        # Mock config manager
        mock_config.get_memory_id.return_value = "test-memory-id"
        
        # Mock memory provider
        mock_memory_instance = MagicMock()
        mock_memory_instance.tools = []
        mock_memory_provider.return_value = mock_memory_instance
        
        # Mock agent response
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(message="Test response from agent")
        mock_agent.return_value = mock_agent_instance
        
        # Test payload
        payload = {
            "prompt": "I need help with my order",
            "customer_id": "test123"
        }
        
        # Execute handler
        result = supervisor_agent_handler(payload, None)
        
        # Verify result
        assert result["status"] == "completed"
        assert result["message"] == "Test response from agent"
        assert result["customer_id"] == "test123"
        assert result["agent_type"] == "supervisor"
    
    @patch('src.customer_support_assistant.agents.supervisor.config_manager')
    @patch('src.customer_support_assistant.agents.supervisor.AgentCoreMemoryToolProvider')
    def test_supervisor_agent_handler_error(self, mock_memory_provider, mock_config):
        """Test supervisor agent error handling."""
        # Mock config manager
        mock_config.get_memory_id.return_value = "test-memory-id"
        
        # Mock memory provider to raise an error
        mock_memory_provider.side_effect = Exception("Memory error")
        
        # Test payload
        payload = {
            "prompt": "Test query",
            "customer_id": "test123"
        }
        
        # Execute handler
        result = supervisor_agent_handler(payload, None)
        
        # Verify error handling
        assert result["status"] == "error"
        assert "error" in result
        assert result["agent_type"] == "supervisor"