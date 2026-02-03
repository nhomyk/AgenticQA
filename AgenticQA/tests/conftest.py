"""Pytest configuration and fixtures for pipeline framework

Provides shared fixtures and configuration for all pipeline tests.
Enables meta-testing of the CI/CD pipeline itself.
"""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_rag():
    """Fixture providing mock RAG system"""
    rag = MagicMock()
    rag.vector_store = MagicMock()
    rag.vector_store.add_document = Mock(return_value=True)
    rag.vector_store.search = Mock(
        return_value=[
            {"text": "similar document 1", "score": 0.95},
            {"text": "similar document 2", "score": 0.87},
        ]
    )
    rag.augment_agent_context = Mock(
        return_value={
            "rag_recommendations": [{"type": "similar_failure", "suggestion": "test suggestion"}],
            "insights_count": 1,
        }
    )
    return rag


@pytest.fixture
def mock_qa_agent():
    """Fixture providing mock QA Agent"""
    agent = MagicMock()
    agent.decide = Mock(
        return_value={
            "agent": "QA",
            "action": "validate_tests",
            "status": "passed",
            "confidence": 0.95,
        }
    )
    return agent


@pytest.fixture
def mock_performance_agent():
    """Fixture providing mock Performance Agent"""
    agent = MagicMock()
    agent.decide = Mock(
        return_value={
            "agent": "Performance",
            "action": "analyze_metrics",
            "status": "passed",
            "confidence": 0.92,
        }
    )
    return agent


@pytest.fixture
def mock_compliance_agent():
    """Fixture providing mock Compliance Agent"""
    agent = MagicMock()
    agent.decide = Mock(
        return_value={
            "agent": "Compliance",
            "action": "validate_compliance",
            "status": "passed",
            "violations": [],
            "confidence": 0.99,
        }
    )
    return agent


@pytest.fixture
def mock_devops_agent():
    """Fixture providing mock DevOps Agent"""
    agent = MagicMock()
    agent.decide = Mock(
        return_value={
            "agent": "DevOps",
            "action": "validate_deployment",
            "status": "ready",
            "checks_passed": 8,
            "confidence": 0.92,
        }
    )
    return agent


@pytest.fixture
def pipeline_context():
    """Fixture providing typical pipeline execution context"""
    return {
        "workflow_id": "21369824538",
        "commit_sha": "abc123def456",
        "branch": "main",
        "trigger": "push",
        "timestamp": "2025-01-26T10:00:00Z",
        "artifact_hash": "hash123",
        "deployment_target": "production",
    }


def pytest_configure(config):
    """Pytest configuration hook"""
    # Register custom markers for categorizing tests
    config.addinivalue_line("markers", "unit: mark test as unit test (isolated, no dependencies)")
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (mocked dependencies)"
    )
    config.addinivalue_line(
        "markers", "pipeline: mark test as pipeline framework test (meta-testing)"
    )
    config.addinivalue_line("markers", "deployment: mark test as deployment readiness test")
    config.addinivalue_line(
        "markers", "critical: mark test as critical for health checks (~40 sec total)"
    )
    config.addinivalue_line("markers", "fast: mark test as fast execution (<1 sec)")
    config.addinivalue_line(
        "markers", "data_integrity: mark test as data structure and type validation"
    )
    config.addinivalue_line("markers", "data_quality: mark test as data content quality check")
    config.addinivalue_line("markers", "data_security: mark test as security and PII validation")
    config.addinivalue_line("markers", "data_snapshot: mark test as before/after comparison")
    config.addinivalue_line(
        "markers", "data_duplication: mark test as duplicate and similarity detection"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection and apply markers"""
    for item in items:
        # Add markers based on test module and function name
        if "test_pipeline_framework" in item.nodeid:
            item.add_marker(pytest.mark.pipeline)

        if "deployment" in item.nodeid.lower():
            item.add_marker(pytest.mark.deployment)

        # Mark critical health check tests
        critical_test_names = [
            "test_linting_tool_works",
            "test_qa_agent_executes",
            "test_rag_system_connected",
            "test_deployment_gates_enforced",
            "test_self_healing_works",
        ]

        for critical_name in critical_test_names:
            if critical_name in item.nodeid:
                item.add_marker(pytest.mark.critical)
                item.add_marker(pytest.mark.fast)
                break
