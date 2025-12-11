"""Test basic project setup and imports."""

import pytest


def test_package_imports():
    """Test that main package can be imported."""
    import src.customer_support_assistant
    
    assert src.customer_support_assistant is not None


def test_subpackage_imports():
    """Test that subpackages can be imported."""
    from src.customer_support_assistant import agents, models, utils
    
    assert agents is not None
    assert models is not None
    assert utils is not None


def test_python_version():
    """Test that we're running on supported Python version."""
    import sys
    
    assert sys.version_info >= (3, 9), "Python 3.9+ required"