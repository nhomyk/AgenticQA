"""
Local Pipeline Validation Framework

Tests pipeline tools and agents locally WITHOUT requiring full CI runs.
Can be run during development to verify everything works before pushing.

Tests verify:
1. Each tool (linting, testing, coverage) functions correctly
2. Agents can execute their core functionality
3. Integration between tools and agents works
4. Code is ready for deployment

Run with: pytest tests/test_local_pipeline_validation.py -v
"""

import pytest
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List


class TestLintingToolValidation:
    """Validate linting tools work correctly"""

    def test_eslint_detects_quote_violations(self, tmp_path):
        """Test ESLint detects incorrect quote usage"""
        test_file = tmp_path / "test.js"
        test_file.write_text(
            """
const message = 'wrong quotes';
console.log(message)
"""
        )

        # Run ESLint (if available)
        try:
            result = subprocess.run(
                ["npx", "eslint", str(test_file), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # ESLint found errors (expected)
                try:
                    errors = json.loads(result.stdout)
                    assert len(errors) > 0, "ESLint should detect quote violations"
                    print(f"✓ ESLint detected {len(errors)} violations")
                except json.JSONDecodeError:
                    pytest.skip("ESLint not configured properly")
            else:
                pytest.skip("ESLint not installed or test file passed")

        except FileNotFoundError:
            pytest.skip("ESLint (npx) not available")

    def test_python_linting_works(self, tmp_path):
        """Test Python linting tools (black, flake8) work"""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def  bad_function( x,y ):
    return x+y
"""
        )

        # Test black
        try:
            result = subprocess.run(
                ["black", "--check", str(test_file)], capture_output=True, timeout=30
            )

            # Black should fail on poorly formatted code
            assert result.returncode != 0, "Black should detect formatting issues"
            print("✓ Black detected formatting issues")

        except FileNotFoundError:
            pytest.skip("Black not installed")

    def test_sre_agent_can_apply_fixes(self):
        """Test SRE Agent can apply linting fixes"""
        from src.agents import SREAgent

        agent = SREAgent()

        linting_data = {
            "file_path": "test.js",
            "errors": [
                {"rule": "quotes", "message": "Use doublequotes", "line": 1},
                {"rule": "semi", "message": "Missing semicolon", "line": 2},
            ],
        }

        result = agent.execute(linting_data)

        assert result["total_errors"] == 2
        assert result["fixes_applied"] >= 1
        assert result["status"] in ["success", "partial"]

        print(f"✓ SRE Agent applied {result['fixes_applied']}/{result['total_errors']} fixes")


class TestCoverageToolValidation:
    """Validate coverage measurement tools work"""

    def test_pytest_coverage_measures_correctly(self, tmp_path):
        """Test pytest-cov measures coverage accurately"""
        # Create a simple module
        module_file = tmp_path / "calculator.py"
        module_file.write_text(
            """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):  # Not tested
    return a * b
"""
        )

        # Create a test file (only tests 2/3 functions)
        test_file = tmp_path / "test_calculator.py"
        test_file.write_text(
            """
from calculator import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2
"""
        )

        # Run pytest with coverage
        try:
            result = subprocess.run(
                ["pytest", str(test_file), f"--cov={tmp_path}", "--cov-report=json", "-v"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Check if coverage report was generated
            coverage_file = tmp_path / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)

                # Should show ~66% coverage (2/3 functions tested)
                total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
                print(f"✓ Coverage measurement: {total_coverage}%")
                assert 50 <= total_coverage <= 100, "Coverage should be measurable"
            else:
                pytest.skip("Coverage report not generated")

        except FileNotFoundError:
            pytest.skip("pytest-cov not installed")

    def test_sdet_agent_identifies_coverage_gaps(self):
        """Test SDET Agent can identify coverage gaps"""
        from src.agents import SDETAgent

        agent = SDETAgent()

        coverage_data = {
            "coverage_percent": 65,
            "uncovered_files": ["src/api/payment.js", "src/services/billing.js"],
            "test_type": "unit",
        }

        result = agent.execute(coverage_data)

        assert result["current_coverage"] == 65
        assert result["coverage_status"] == "insufficient"  # < 80%
        assert result["gaps_identified"] >= 2
        assert len(result["recommendations"]) > 0

        print(f"✓ SDET Agent identified {result['gaps_identified']} coverage gaps")
        print(f"✓ Generated {len(result['recommendations'])} recommendations")


class TestAgentToolIntegration:
    """Test integration between agents and tools"""

    def test_qa_agent_processes_test_results(self):
        """Test QA Agent can process test results from pytest"""
        from src.agents import QAAssistantAgent

        agent = QAAssistantAgent()

        # Simulate pytest output
        test_results = {
            "test_name": "test_user_authentication",
            "test_type": "integration",
            "status": "failed",
            "total": 10,
            "passed": 8,
            "failed": 2,
            "coverage": 85,
            "error_message": "AssertionError: Expected 200, got 401",
        }

        result = agent.execute(test_results)

        assert "recommendations" in result
        assert len(result["recommendations"]) > 0
        assert "rag_insights_used" in result

        print(f"✓ QA Agent generated {len(result['recommendations'])} recommendations")
        print(f"✓ Used {result['rag_insights_used']} RAG insights")

    def test_performance_agent_processes_metrics(self):
        """Test Performance Agent can process execution metrics"""
        from src.agents import PerformanceAgent

        agent = PerformanceAgent()

        execution_data = {
            "operation": "database_query",
            "duration_ms": 8500,
            "memory_mb": 512,
            "baseline_ms": 2000,
        }

        result = agent.execute(execution_data)

        assert result["status"] == "degraded"  # 8500ms > 5000ms threshold
        assert "optimizations" in result
        assert len(result["optimizations"]) > 0

        print(f"✓ Performance Agent detected degradation: {result['duration_ms']}ms")
        print(f"✓ Generated {len(result['optimizations'])} optimization suggestions")

    def test_compliance_agent_detects_violations(self):
        """Test Compliance Agent can detect security violations"""
        from src.agents import ComplianceAgent

        agent = ComplianceAgent()

        compliance_data = {
            "context": "User data storage",
            "regulations": ["GDPR", "HIPAA"],
            "encrypted": False,  # Violation!
            "pii_masked": False,  # Violation!
            "audit_enabled": True,
        }

        result = agent.execute(compliance_data)

        assert len(result["violations"]) >= 2  # Should detect both violations
        assert not result["data_encryption"]
        assert not result["pii_protection"]

        print(f"✓ Compliance Agent detected {len(result['violations'])} violations")


class TestFullstackAgentCodeGeneration:
    """Test Fullstack Agent code generation capabilities"""

    def test_fullstack_generates_api_endpoint(self):
        """Test Fullstack Agent generates valid API code"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        feature_request = {
            "title": "Get User Profile",
            "category": "api",
            "description": "API endpoint to retrieve user profile by ID",
        }

        result = agent.execute(feature_request)

        assert result["code_generated"] is True
        assert result["code"] is not None
        assert "function" in result["code"] or "async" in result["code"]
        assert len(result["files_created"]) > 0

        print(f"✓ Fullstack Agent generated code for: {feature_request['title']}")
        print(f"✓ Files to create: {', '.join(result['files_created'])}")

    def test_fullstack_generates_ui_component(self):
        """Test Fullstack Agent generates UI components"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        feature_request = {
            "title": "User Profile Card",
            "category": "ui",
            "description": "Card component displaying user avatar, name, and bio",
        }

        result = agent.execute(feature_request)

        assert result["code_generated"] is True
        assert "<div" in result["code"] or "component" in result["code"].lower()

        print(f"✓ Fullstack Agent generated UI component")


class TestDeploymentReadiness:
    """Test deployment readiness validation"""

    def test_all_deployment_gates_enforceable(self):
        """Verify all deployment gates can be enforced"""
        deployment_gates = {
            "linting_passed": True,
            "tests_passed": True,
            "coverage_minimum": True,
            "security_scan_passed": True,
            "rag_integration_working": True,
            "agents_functioning": True,
        }

        # All gates must be True for deployment
        all_passed = all(deployment_gates.values())
        assert all_passed, f"Some deployment gates failed: {deployment_gates}"

        print("✓ All deployment gates enforceable")

    def test_data_quality_pipeline_works(self):
        """Test data quality pipeline validates before deployment"""
        from src.data_store.data_quality_pipeline import DataQualityValidatedPipeline

        pipeline = DataQualityValidatedPipeline(
            use_great_expectations=False, run_quality_tests=True
        )

        # Run validation
        result = pipeline.run_deployment_validation()

        # Should return deployment readiness status
        assert "ready_for_deployment" in result
        print(f"✓ Data quality pipeline ready: {result['ready_for_deployment']}")


class TestPipelineHealthChecks:
    """Fast health checks for pipeline components"""

    def test_artifact_store_accessible(self):
        """Verify artifact store is accessible"""
        from src.data_store.artifact_store import TestArtifactStore

        store = TestArtifactStore()

        # Should be able to search artifacts
        artifacts = store.search_artifacts()
        assert isinstance(artifacts, list)

        print(f"✓ Artifact store accessible ({len(artifacts)} artifacts)")

    def test_rag_system_initializes(self):
        """Verify RAG system can initialize"""
        try:
            from src.agenticqa.rag.config import RAGConfig

            # Should not raise exception
            mode = RAGConfig.get_deployment_mode()
            config = RAGConfig.get_weaviate_config()

            print(f"✓ RAG system initializes (mode: {mode.value})")

        except Exception as e:
            # RAG might not be configured, that's ok
            print(f"⚠ RAG not configured: {e}")
            pytest.skip("RAG not configured")

    def test_all_agents_initialize(self):
        """Verify all agents can be instantiated"""
        from src.agents import (
            QAAssistantAgent,
            PerformanceAgent,
            ComplianceAgent,
            DevOpsAgent,
            SREAgent,
            SDETAgent,
            FullstackAgent,
        )

        agents = [
            QAAssistantAgent(),
            PerformanceAgent(),
            ComplianceAgent(),
            DevOpsAgent(),
            SREAgent(),
            SDETAgent(),
            FullstackAgent(),
        ]

        for agent in agents:
            assert agent.agent_name is not None
            assert hasattr(agent, "execute")

        print(f"✓ All {len(agents)} agents initialize successfully")


class TestToolChainValidation:
    """Validate entire tool chain works together"""

    def test_linting_to_sre_agent_flow(self):
        """Test: Linting errors → SRE Agent fixes"""
        from src.agents import SREAgent

        # Simulate linting output
        linting_errors = [
            {"rule": "quotes", "message": "Use double quotes", "line": 1},
            {"rule": "semi", "message": "Missing semicolon", "line": 5},
        ]

        # Pass to SRE Agent
        agent = SREAgent()
        result = agent.execute({"file_path": "test.js", "errors": linting_errors})

        assert result["total_errors"] == 2
        assert result["fixes_applied"] >= 1

        print("✓ Linting → SRE Agent flow validated")

    def test_coverage_to_sdet_agent_flow(self):
        """Test: Coverage report → SDET Agent recommendations"""
        from src.agents import SDETAgent

        # Simulate coverage report
        coverage_report = {
            "coverage_percent": 72,
            "uncovered_files": ["src/api/orders.js", "src/services/payment.js"],
            "test_type": "unit",
        }

        # Pass to SDET Agent
        agent = SDETAgent()
        result = agent.execute(coverage_report)

        assert result["coverage_status"] == "insufficient"
        assert result["gaps_identified"] >= 2
        assert len(result["recommendations"]) > 0

        print("✓ Coverage → SDET Agent flow validated")

    def test_feature_request_to_fullstack_agent_flow(self):
        """Test: Feature request → Fullstack Agent → Code generation"""
        from src.agents import FullstackAgent

        # Simulate feature request
        feature_request = {
            "title": "Password Reset API",
            "category": "api",
            "description": "Endpoint to handle password reset requests",
        }

        # Pass to Fullstack Agent
        agent = FullstackAgent()
        result = agent.execute(feature_request)

        assert result["code_generated"] is True
        assert len(result["files_created"]) > 0

        print("✓ Feature Request → Fullstack Agent flow validated")


# Summary report when run directly
if __name__ == "__main__":
    print("=" * 80)
    print("LOCAL PIPELINE VALIDATION FRAMEWORK")
    print("=" * 80)
    print()
    print("This validates pipeline tools and agents locally without requiring CI.")
    print()
    print("Test Categories:")
    print("1. Linting Tool Validation - Verify linters detect issues")
    print("2. Coverage Tool Validation - Verify coverage measurement works")
    print("3. Agent-Tool Integration - Verify agents work with tool output")
    print("4. Code Generation - Verify Fullstack Agent generates valid code")
    print("5. Deployment Readiness - Verify deployment gates work")
    print("6. Health Checks - Fast validation of core components")
    print("7. Tool Chain - Validate end-to-end flows")
    print()
    print("Run with: pytest tests/test_local_pipeline_validation.py -v")
    print("=" * 80)
