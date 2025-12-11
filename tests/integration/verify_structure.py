#!/usr/bin/env python3
"""
Verification script to check all migrated tests work with new structure.

This script:
1. Verifies all test files can be imported
2. Checks that utilities are accessible
3. Reports any import or structural issues
"""

import sys
import os
import importlib
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def verify_imports():
    """Verify all test modules can be imported."""
    print("=" * 60)
    print("Verifying Test Structure and Imports")
    print("=" * 60)
    print()
    
    # Test files to verify
    test_modules = [
        # Setup
        "tests.integration.00_setup.test_setup",
        
        # Infrastructure tests
        "tests.integration.01_infrastructure.test_stacks",
        "tests.integration.01_infrastructure.test_runtimes",
        "tests.integration.01_infrastructure.test_gateways",
        "tests.integration.01_infrastructure.test_knowledge_bases",
        "tests.integration.01_infrastructure.test_cognito",
        "tests.integration.01_infrastructure.test_memory",
        
        # Sub-agent tests
        "tests.integration.02_sub_agents.test_order_management",
        "tests.integration.02_sub_agents.test_personalization",
        "tests.integration.02_sub_agents.test_product_recommendation",
        "tests.integration.02_sub_agents.test_troubleshooting",
        
        # Supervisor tests
        "tests.integration.03_supervisor.test_supervisor_basic",
        "tests.integration.03_supervisor.test_delegation_order",
        "tests.integration.03_supervisor.test_delegation_personalization",
        "tests.integration.03_supervisor.test_delegation_product",
        "tests.integration.03_supervisor.test_delegation_troubleshooting",
    ]
    
    # Utility modules to verify
    utility_modules = [
        "tests.integration.utils.config",
        "tests.integration.utils.aws_operations",
        "tests.integration.utils.authentication",
        "tests.integration.utils.runtime_operations",
        "tests.integration.utils.log_operations",
        "tests.integration.utils.validation",
        "tests.integration.utils.errors",
    ]
    
    passed = 0
    failed = 0
    issues = []
    
    print("Verifying utility modules...")
    print("-" * 60)
    for module_name in utility_modules:
        try:
            module = importlib.import_module(module_name)
            print(f"  ✓ {module_name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {module_name}: {str(e)}")
            failed += 1
            issues.append(f"{module_name}: {str(e)}")
    
    print()
    print("Verifying test modules...")
    print("-" * 60)
    for module_name in test_modules:
        try:
            module = importlib.import_module(module_name)
            print(f"  ✓ {module_name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {module_name}: {str(e)}")
            failed += 1
            issues.append(f"{module_name}: {str(e)}")
    
    print()
    print("=" * 60)
    print("Verification Summary")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if issues:
        print()
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print()
        print("✓ All modules can be imported successfully!")
        print()
        print("Next steps:")
        print("  1. Run individual test files to verify functionality")
        print("  2. Run full test suite: python tests/integration/run_all_tests.py")
        return 0


def verify_utility_functions():
    """Verify key utility functions are accessible."""
    print()
    print("=" * 60)
    print("Verifying Utility Functions")
    print("=" * 60)
    print()
    
    try:
        from tests.integration.utils import (
            load_config,
            save_config,
            validate_config,
            extract_stack_outputs,
            create_test_user,
            get_jwt_token,
            invoke_agentcore_runtime,
            get_cloudwatch_logs,
            check_delegation_in_logs,
            TestError,
            ErrorCategory
        )
        
        print("✓ All key utility functions are accessible")
        print()
        print("Available functions:")
        print("  • load_config, save_config, validate_config")
        print("  • extract_stack_outputs")
        print("  • create_test_user, get_jwt_token")
        print("  • invoke_agentcore_runtime")
        print("  • get_cloudwatch_logs")
        print("  • check_delegation_in_logs")
        print("  • TestError, ErrorCategory")
        
        return 0
        
    except ImportError as e:
        print(f"✗ Failed to import utility functions: {str(e)}")
        return 1


def main():
    """Main verification function."""
    result1 = verify_imports()
    result2 = verify_utility_functions()
    
    return max(result1, result2)


if __name__ == '__main__':
    sys.exit(main())
