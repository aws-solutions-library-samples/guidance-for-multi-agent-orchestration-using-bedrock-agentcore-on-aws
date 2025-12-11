# Integration Tests

This directory contains the reorganized integration test suite for the Customer Support Assistant multi-agent system.

## Structure

```
tests/integration/
├── 00_setup/              # Setup and configuration extraction
├── 01_infrastructure/     # Infrastructure validation tests
├── 02_sub_agents/         # Individual agent runtime tests
├── 03_supervisor/         # Supervisor orchestration tests
├── utils/                 # Shared utility modules
├── test_config.json       # Generated configuration (created by setup)
├── run_all_tests.py       # Master test runner
└── verify_structure.py    # Import verification script
```

## Quick Start

### 1. Setup (First Time Only)

Extract configuration from deployed CloudFormation stacks:

```bash
python3 tests/integration/00_setup/test_setup.py
```

This creates `test_config.json` with all required ARNs, IDs, and uses existing test users from `scripts/test_users_config.json` (created during deployment).

### 2. Run All Tests

Execute the complete test suite in order:

```bash
python3 tests/integration/run_all_tests.py
```

Tests run in phases:
1. **Setup** - Extract configuration and load test user credentials
2. **Infrastructure** - Validate CloudFormation, Runtimes, Gateways, etc.
3. **Sub-Agents** - Test each agent independently
4. **Supervisor** - Test orchestration and delegation

### 3. Run Specific Test Categories

**Infrastructure tests only:**
```bash
python3 tests/integration/run_all_tests.py --phase infrastructure
```

**Sub-agent tests only:**
```bash
python3 tests/integration/run_all_tests.py --phase sub-agents
```

**Supervisor tests only:**
```bash
python3 tests/integration/run_all_tests.py --phase supervisor
```

### 4. Run Individual Tests

**Infrastructure tests (standalone scripts):**
```bash
python3 tests/integration/01_infrastructure/test_stacks.py
python3 tests/integration/01_infrastructure/test_runtimes.py
```

**Sub-agent tests (pytest):**
```bash
python3 -m pytest tests/integration/02_sub_agents/test_order_management.py -v
python3 -m pytest tests/integration/02_sub_agents/test_personalization.py -v
```

**Supervisor tests (pytest):**
```bash
python3 -m pytest tests/integration/03_supervisor/test_supervisor_basic.py -v
python3 -m pytest tests/integration/03_supervisor/test_delegation_order.py -v
```

## Test Categories

### Infrastructure Tests (01_infrastructure/)

Validates that all infrastructure components are properly deployed:

- **test_stacks.py** - CloudFormation stacks status
- **test_runtimes.py** - AgentCore Runtimes status
- **test_gateways.py** - Gateway configuration
- **test_knowledge_bases.py** - Knowledge Base status
- **test_cognito.py** - Cognito User Pool configuration
- **test_memory.py** - Memory service availability

### Sub-Agent Tests (02_sub_agents/)

Tests each agent runtime independently with JWT authentication and tool usage:

- **test_order_management.py** - Order Management agent
- **test_personalization.py** - Personalization agent
- **test_product_recommendation.py** - Product Recommendation agent
- **test_troubleshooting.py** - Troubleshooting agent

Each test verifies:
1. Runtime accepts JWT authentication
2. Runtime responds to queries
3. Agent invokes Gateway tools
4. Tool results are returned
5. No sensitive data in logs

### Supervisor Tests (03_supervisor/)

Tests supervisor orchestration and delegation:

- **test_supervisor_basic.py** - Basic supervisor functionality
- **test_delegation_order.py** - Delegation to Order Management
- **test_delegation_personalization.py** - Delegation to Personalization
- **test_delegation_product.py** - Delegation to Product Recommendation
- **test_delegation_troubleshooting.py** - Delegation to Troubleshooting

Each delegation test verifies:
1. Supervisor receives query
2. Supervisor makes HTTP POST to sub-agent
3. JWT is propagated
4. Sub-agent processes request
5. Response is returned

## Utility Modules (utils/)

Shared helper functions organized by domain:

- **config.py** - Configuration loading and validation
- **aws_operations.py** - CloudFormation and AWS service operations
- **authentication.py** - Cognito JWT operations
- **runtime_operations.py** - AgentCore Runtime invocation
- **log_operations.py** - CloudWatch log queries
- **validation.py** - Response and delegation validation
- **errors.py** - Error classes and categories

All utilities are re-exported through `utils/__init__.py` for easy importing:

```python
from tests.integration.utils import (
    load_config,
    get_jwt_token,
    invoke_agentcore_runtime,
    get_cloudwatch_logs,
    check_delegation_in_logs,
    TestError,
    ErrorCategory
)
```

## Verification

Verify all imports and structure:

```bash
python3 tests/integration/verify_structure.py
```

This checks:
- All utility modules can be imported
- All test modules can be imported
- All key functions are accessible

## Troubleshooting

### Configuration Not Found

If you see "test_config.json not found", run the setup:

```bash
python3 tests/integration/00_setup/test_setup.py
```

### Import Errors

Verify the structure:

```bash
python3 tests/integration/verify_structure.py
```

### Test Failures

The master test runner provides detailed error messages with troubleshooting guidance based on error category:

- **Infrastructure** - Check CloudFormation stacks
- **Authentication** - Verify Cognito configuration
- **Runtime** - Check Runtime status and logs
- **Gateway** - Verify Gateway configuration
- **Agent** - Check agent logs for errors

### Log Verification

All tests verify behavior through CloudWatch logs. If log verification fails:

1. Check the log group exists
2. Verify log retention settings
3. Increase wait time for log propagation
4. Check CloudWatch permissions

## Requirements

- Python 3.9+
- boto3
- requests
- pytest (for sub-agent and supervisor tests)
- AWS credentials configured
- All infrastructure deployed via CDK
