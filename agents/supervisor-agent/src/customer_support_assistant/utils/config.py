"""Configuration utilities for Customer Support Assistant."""

import os
import boto3
from typing import Optional
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Simple configuration manager for customer support."""
    
    def __init__(self):
        self._cloudformation_client: Optional[boto3.client] = None
        self._memory_id_cache: Optional[str] = None
        self._personalization_agent_runtime_id_cache: Optional[str] = None
        self._agent_workload_name_cache: Optional[str] = None
    
    @property
    def cloudformation_client(self):
        """Lazy initialization of CloudFormation client."""
        if self._cloudformation_client is None:
            self._cloudformation_client = boto3.client('cloudformation')
        return self._cloudformation_client
    
    def get_memory_id(self) -> str:
        """Retrieve AgentCore Memory ID from environment variables or fallback methods."""
        if not self._memory_id_cache:
            # First try environment variable (set by AgentCore deployment)
            memory_id = os.getenv('MEMORY_ID')
            if memory_id:
                self._memory_id_cache = memory_id
                logger.info("Retrieved memory ID from environment variable")
                return self._memory_id_cache
            
            # Try to get from SSM parameter
            try:
                ssm_client = boto3.client('ssm')
                # Use dynamic stack name from environment
                stack_name = os.getenv('ORCHESTRATOR_STACK_NAME', 'CustomerSupportAssistantStack')
                response = ssm_client.get_parameter(Name=f'/{stack_name}/memory-instance-id')
                self._memory_id_cache = response['Parameter']['Value']
                logger.info("Retrieved memory ID from SSM parameter store")
                return self._memory_id_cache
            except ClientError:
                logger.info("SSM parameter not found, trying CloudFormation outputs")
            
            # Fallback to CloudFormation outputs
            stack_name = os.getenv('CLOUDFORMATION_STACK_NAME', 'CustomerSupportAssistantStack')
            
            try:
                response = self.cloudformation_client.describe_stacks(StackName=stack_name)
                stacks = response.get('Stacks', [])
                
                if not stacks:
                    raise ValueError(f"CloudFormation stack '{stack_name}' not found")
                
                outputs = stacks[0].get('Outputs', [])
                for output in outputs:
                    if output.get('OutputKey') == 'MemoryCustomResourceId':
                        self._memory_id_cache = output.get('OutputValue')
                        logger.info("Retrieved memory ID from CloudFormation outputs")
                        break
                
                if not self._memory_id_cache:
                    raise ValueError("MemoryCustomResourceId output not found in CloudFormation stack")
            except Exception as e:
                logger.error(f"Failed to retrieve memory ID from CloudFormation: {e}")
                raise ValueError("Could not retrieve memory ID from any source")
        
        return self._memory_id_cache
    
    def get_personalization_agent_runtime_id(self) -> str:
        """
        Retrieve Personalization Agent Runtime ID from environment variables.
        
        Returns:
            Personalization agent runtime ID
            
        Raises:
            ValueError: If runtime ID cannot be retrieved
        """
        if not self._personalization_agent_runtime_id_cache:
            # Try environment variable first
            runtime_id = os.getenv('PERSONALIZATION_AGENT_RUNTIME_ID')
            if runtime_id:
                self._personalization_agent_runtime_id_cache = runtime_id
                logger.info("Retrieved personalization agent runtime ID from environment variable")
                return self._personalization_agent_runtime_id_cache
            
            # Try SSM parameter as fallback
            try:
                ssm_client = boto3.client('ssm')
                # Get parameter name from environment variable (set by supervisor CDK)
                param_name = os.getenv('PERSONALIZATION_AGENT_RUNTIME_ID_PARAM')
                if not param_name:
                    raise ValueError("PERSONALIZATION_AGENT_RUNTIME_ID_PARAM environment variable not set")
                
                response = ssm_client.get_parameter(Name=param_name)
                self._personalization_agent_runtime_id_cache = response['Parameter']['Value']
                logger.info("Retrieved personalization agent runtime ID from SSM parameter store")
                return self._personalization_agent_runtime_id_cache
            except ClientError as e:
                logger.error(f"Failed to retrieve personalization agent runtime ID: {e}")
                raise ValueError("Could not retrieve personalization agent runtime ID from any source")
        
        return self._personalization_agent_runtime_id_cache
    
    def get_agent_workload_name(self) -> str:
        """
        Retrieve Agent Workload Name from environment variables.
        
        Returns:
            Agent workload name for workload identity
            
        Raises:
            ValueError: If workload name cannot be retrieved
        """
        if not self._agent_workload_name_cache:
            # Try environment variable first
            workload_name = os.getenv('AGENT_WORKLOAD_NAME')
            if workload_name:
                self._agent_workload_name_cache = workload_name
                logger.info("Retrieved agent workload name from environment variable")
                return self._agent_workload_name_cache
            
            # Try SSM parameter as fallback
            try:
                ssm_client = boto3.client('ssm')
                # Use dynamic stack name from environment
                stack_name = os.getenv('ORCHESTRATOR_STACK_NAME', 'CustomerSupportAssistantStack')
                response = ssm_client.get_parameter(
                    Name=f'/{stack_name}/agent-workload-name'
                )
                self._agent_workload_name_cache = response['Parameter']['Value']
                logger.info("Retrieved agent workload name from SSM parameter store")
                return self._agent_workload_name_cache
            except ClientError as e:
                logger.error(f"Failed to retrieve agent workload name: {e}")
                raise ValueError("Could not retrieve agent workload name from any source")
        
        return self._agent_workload_name_cache


# Global config manager instance
config_manager = ConfigManager()