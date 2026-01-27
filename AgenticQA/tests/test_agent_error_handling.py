"""
Error-Throwing Tests for Agent Functionality

These tests intentionally introduce errors to verify agents respond correctly:
- SRE Agent: Detects and fixes linting errors, triggers new workflow
- Fullstack Agent: Generates code from feature requests
- SDET Agent: Identifies coverage gaps and recommends new tests

These tests validate the self-healing capabilities of the pipeline.
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from typing import Dict, Any


class TestSREAgentLintingFixes:
    """Test SRE Agent detects and fixes linting errors"""

    def test_sre_agent_exists_and_initializes(self):
        """Verify SRE Agent can be instantiated"""
        from src.agents import SREAgent

        agent = SREAgent()
        assert agent.agent_name == "SRE_Agent"
        assert agent.use_data_store is True
        print("✓ SRE Agent initialized successfully")

    def test_sre_agent_detects_linting_errors(self):
        """Test SRE Agent detects linting errors in code"""
        from src.agents import SREAgent

        agent = SREAgent()

        # Simulate linting errors
        linting_data = {
            "file_path": "src/test_file.js",
            "errors": [
                {
                    "rule": "quotes",
                    "message": "Strings must use doublequote",
                    "line": 10,
                    "severity": "error"
                },
                {
                    "rule": "semi",
                    "message": "Missing semicolon",
                    "line": 15,
                    "severity": "error"
                },
                {
                    "rule": "no-unused-vars",
                    "message": "Unused variable 'foo'",
                    "line": 20,
                    "severity": "warning"
                }
            ]
        }

        result = agent.execute(linting_data)

        # Verify agent detected errors
        assert result["total_errors"] == 3
        assert result["fixes_applied"] >= 0  # Should attempt to fix
        assert result["status"] in ["success", "partial"]
        print(f"✓ SRE Agent detected {result['total_errors']} errors and applied {result['fixes_applied']} fixes")

    def test_sre_agent_applies_quote_fix(self):
        """Test SRE Agent fixes quote-related linting errors"""
        from src.agents import SREAgent

        agent = SREAgent()

        linting_data = {
            "file_path": "src/test.js",
            "errors": [
                {
                    "rule": "quotes",
                    "message": "Strings must use doublequote",
                    "line": 5
                }
            ]
        }

        result = agent.execute(linting_data)

        assert result["fixes_applied"] >= 1
        assert any("quotes" in str(fix) for fix in result["fixes"])
        print("✓ SRE Agent applied quote fix")

    def test_sre_agent_applies_semicolon_fix(self):
        """Test SRE Agent fixes missing semicolons"""
        from src.agents import SREAgent

        agent = SREAgent()

        linting_data = {
            "file_path": "src/test.js",
            "errors": [
                {
                    "rule": "semi",
                    "message": "Missing semicolon",
                    "line": 10
                }
            ]
        }

        result = agent.execute(linting_data)

        assert result["fixes_applied"] >= 1
        assert any("semi" in str(fix) for fix in result["fixes"])
        print("✓ SRE Agent applied semicolon fix")

    def test_sre_agent_learns_from_rag(self):
        """Test SRE Agent uses RAG insights when available"""
        from src.agents import SREAgent

        agent = SREAgent()

        # If RAG is not available, skip this test
        if not agent.use_rag or agent.rag is None:
            pytest.skip("RAG not configured - skipping RAG-enhanced test")

        linting_data = {
            "file_path": "src/test.js",
            "errors": [
                {
                    "rule": "indent",
                    "message": "Expected indentation of 2 spaces",
                    "line": 15
                }
            ]
        }

        result = agent.execute(linting_data)

        # Should track RAG insights usage
        assert "rag_insights_used" in result
        print(f"✓ SRE Agent used {result['rag_insights_used']} RAG insights")

    def test_sre_agent_handles_multiple_error_types(self):
        """Test SRE Agent handles complex linting scenarios"""
        from src.agents import SREAgent

        agent = SREAgent()

        linting_data = {
            "file_path": "src/complex.js",
            "errors": [
                {"rule": "quotes", "message": "Use doublequotes", "line": 1},
                {"rule": "semi", "message": "Missing semicolon", "line": 2},
                {"rule": "indent", "message": "Bad indentation", "line": 3},
                {"rule": "no-unused-vars", "message": "Unused var", "line": 4},
            ]
        }

        result = agent.execute(linting_data)

        assert result["total_errors"] == 4
        assert result["fixes_applied"] >= 3  # Should fix most common errors
        print(f"✓ SRE Agent handled {result['total_errors']} errors, applied {result['fixes_applied']} fixes")


class TestFullstackAgentCodeGeneration:
    """Test Fullstack Agent generates code from feature requests"""

    def test_fullstack_agent_exists_and_initializes(self):
        """Verify Fullstack Agent can be instantiated"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()
        assert agent.agent_name == "Fullstack_Agent"
        assert agent.use_data_store is True
        print("✓ Fullstack Agent initialized successfully")

    def test_fullstack_agent_generates_api_code(self):
        """Test Fullstack Agent generates API endpoint code"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        feature_request = {
            "title": "Create User Profile",
            "category": "api",
            "description": "API endpoint to create user profile with name and email"
        }

        result = agent.execute(feature_request)

        assert result["code_generated"] is True
        assert result["code"] is not None
        assert "async function" in result["code"] or "function" in result["code"]
        assert len(result["files_created"]) > 0
        print(f"✓ Fullstack Agent generated API code, files: {result['files_created']}")

    def test_fullstack_agent_generates_ui_code(self):
        """Test Fullstack Agent generates UI component code"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        feature_request = {
            "title": "User Dashboard Widget",
            "category": "ui",
            "description": "Dashboard widget showing user statistics and activity"
        }

        result = agent.execute(feature_request)

        assert result["code_generated"] is True
        assert result["code"] is not None
        assert "<div" in result["code"] or "component" in result["code"].lower()
        print(f"✓ Fullstack Agent generated UI code, files: {result['files_created']}")

    def test_fullstack_agent_generates_general_feature(self):
        """Test Fullstack Agent generates general feature code"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        feature_request = {
            "title": "Data Validation Utility",
            "category": "utility",
            "description": "Utility to validate email addresses and phone numbers"
        }

        result = agent.execute(feature_request)

        assert result["code_generated"] is True
        assert result["code"] is not None
        assert "function" in result["code"]
        print("✓ Fullstack Agent generated utility code")

    def test_fullstack_agent_learns_from_rag(self):
        """Test Fullstack Agent uses RAG insights for better code generation"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        if not agent.use_rag or agent.rag is None:
            pytest.skip("RAG not configured")

        feature_request = {
            "title": "Authentication Middleware",
            "category": "api",
            "description": "Middleware to verify JWT tokens"
        }

        result = agent.execute(feature_request)

        assert "rag_insights_used" in result
        print(f"✓ Fullstack Agent used {result['rag_insights_used']} RAG insights")

    def test_fullstack_agent_handles_complex_requests(self):
        """Test Fullstack Agent handles complex feature requests"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        feature_request = {
            "title": "Multi-Step Form with Validation",
            "category": "ui",
            "description": "Three-step form with validation, progress indicator, and data persistence"
        }

        result = agent.execute(feature_request)

        assert result["code_generated"] is True
        assert result["status"] == "success"
        print("✓ Fullstack Agent handled complex feature request")


class TestSDETAgentCoverageAnalysis:
    """Test SDET Agent identifies coverage gaps and recommends tests"""

    def test_sdet_agent_exists_and_initializes(self):
        """Verify SDET Agent can be instantiated"""
        from src.agents import SDETAgent

        agent = SDETAgent()
        assert agent.agent_name == "SDET_Agent"
        assert agent.use_data_store is True
        print("✓ SDET Agent initialized successfully")

    def test_sdet_agent_detects_insufficient_coverage(self):
        """Test SDET Agent identifies insufficient test coverage"""
        from src.agents import SDETAgent

        agent = SDETAgent()

        coverage_data = {
            "coverage_percent": 65,
            "uncovered_files": [
                "src/api/users.js",
                "src/services/auth.js",
                "src/utils/validation.js"
            ],
            "test_type": "unit"
        }

        result = agent.execute(coverage_data)

        assert result["current_coverage"] == 65
        assert result["coverage_status"] == "insufficient"  # < 80%
        assert result["gaps_identified"] >= 3
        print(f"✓ SDET Agent detected insufficient coverage: {result['current_coverage']}%")

    def test_sdet_agent_detects_adequate_coverage(self):
        """Test SDET Agent recognizes adequate coverage"""
        from src.agents import SDETAgent

        agent = SDETAgent()

        coverage_data = {
            "coverage_percent": 92,
            "uncovered_files": [],
            "test_type": "unit"
        }

        result = agent.execute(coverage_data)

        assert result["current_coverage"] == 92
        assert result["coverage_status"] == "adequate"  # >= 80%
        print(f"✓ SDET Agent recognized adequate coverage: {result['current_coverage']}%")

    def test_sdet_agent_identifies_high_priority_gaps(self):
        """Test SDET Agent prioritizes critical untested files"""
        from src.agents import SDETAgent

        agent = SDETAgent()

        coverage_data = {
            "coverage_percent": 70,
            "uncovered_files": [
                "src/api/payment.js",  # Should be high priority
                "src/services/billing.js",  # Should be high priority
                "src/utils/logger.js"  # Lower priority
            ],
            "test_type": "integration"
        }

        result = agent.execute(coverage_data)

        assert result["gaps_identified"] >= 3

        # Check for high-priority gaps
        high_priority = [g for g in result["gaps"] if g.get("priority") == "high"]
        assert len(high_priority) >= 2  # payment and billing should be high priority
        print(f"✓ SDET Agent identified {len(high_priority)} high-priority coverage gaps")

    def test_sdet_agent_generates_test_recommendations(self):
        """Test SDET Agent provides actionable test recommendations"""
        from src.agents import SDETAgent

        agent = SDETAgent()

        coverage_data = {
            "coverage_percent": 55,
            "uncovered_files": [
                "src/api/orders.js",
                "src/api/products.js",
                "src/services/inventory.js"
            ],
            "test_type": "unit"
        }

        result = agent.execute(coverage_data)

        assert len(result["recommendations"]) > 0
        # Should recommend adding tests for high-priority files
        assert any("test" in rec.lower() for rec in result["recommendations"])
        print(f"✓ SDET Agent generated {len(result['recommendations'])} recommendations")

    def test_sdet_agent_learns_from_rag(self):
        """Test SDET Agent uses RAG insights for coverage analysis"""
        from src.agents import SDETAgent

        agent = SDETAgent()

        if not agent.use_rag or agent.rag is None:
            pytest.skip("RAG not configured")

        coverage_data = {
            "coverage_percent": 75,
            "uncovered_files": ["src/api/analytics.js"],
            "test_type": "integration"
        }

        result = agent.execute(coverage_data)

        assert "rag_insights_used" in result
        print(f"✓ SDET Agent used {result['rag_insights_used']} RAG insights")


class TestAgentErrorRecovery:
    """Test agents handle errors gracefully and recover"""

    def test_sre_agent_handles_empty_error_list(self):
        """Test SRE Agent handles no errors gracefully"""
        from src.agents import SREAgent

        agent = SREAgent()

        linting_data = {
            "file_path": "src/clean_file.js",
            "errors": []
        }

        result = agent.execute(linting_data)

        assert result["total_errors"] == 0
        assert result["fixes_applied"] == 0
        assert result["status"] == "success"
        print("✓ SRE Agent handled empty error list")

    def test_fullstack_agent_handles_invalid_category(self):
        """Test Fullstack Agent handles unknown category"""
        from src.agents import FullstackAgent

        agent = FullstackAgent()

        feature_request = {
            "title": "Unknown Feature",
            "category": "unknown_category",
            "description": "Test unknown category handling"
        }

        result = agent.execute(feature_request)

        # Should still generate code with default template
        assert result["code_generated"] is True
        assert result["status"] == "success"
        print("✓ Fullstack Agent handled unknown category")

    def test_sdet_agent_handles_perfect_coverage(self):
        """Test SDET Agent handles 100% coverage"""
        from src.agents import SDETAgent

        agent = SDETAgent()

        coverage_data = {
            "coverage_percent": 100,
            "uncovered_files": [],
            "test_type": "unit"
        }

        result = agent.execute(coverage_data)

        assert result["coverage_status"] == "adequate"
        assert result["gaps_identified"] == 0
        print("✓ SDET Agent handled perfect coverage")


class TestAgentIntegration:
    """Test agents work together in pipeline scenarios"""

    def test_sre_then_sdet_workflow(self):
        """Test SRE fixes linting, then SDET checks coverage"""
        from src.agents import SREAgent, SDETAgent

        # Step 1: SRE fixes linting errors
        sre = SREAgent()
        linting_data = {
            "file_path": "src/feature.js",
            "errors": [
                {"rule": "quotes", "message": "Use doublequotes", "line": 1},
                {"rule": "semi", "message": "Missing semicolon", "line": 2}
            ]
        }

        sre_result = sre.execute(linting_data)
        assert sre_result["status"] in ["success", "partial"]

        # Step 2: SDET checks coverage after fixes
        sdet = SDETAgent()
        coverage_data = {
            "coverage_percent": 88,
            "uncovered_files": [],
            "test_type": "unit"
        }

        sdet_result = sdet.execute(coverage_data)
        assert sdet_result["coverage_status"] == "adequate"

        print("✓ SRE → SDET workflow completed successfully")

    def test_fullstack_then_sdet_workflow(self):
        """Test Fullstack generates code, then SDET checks coverage"""
        from src.agents import FullstackAgent, SDETAgent

        # Step 1: Fullstack generates new feature
        fullstack = FullstackAgent()
        feature_request = {
            "title": "New API Endpoint",
            "category": "api",
            "description": "Create new endpoint"
        }

        fullstack_result = fullstack.execute(feature_request)
        assert fullstack_result["code_generated"] is True

        # Step 2: SDET identifies that new code needs tests
        sdet = SDETAgent()
        coverage_data = {
            "coverage_percent": 75,  # Dropped due to new code
            "uncovered_files": ["routes/feature.js"],
            "test_type": "integration"
        }

        sdet_result = sdet.execute(coverage_data)
        assert sdet_result["gaps_identified"] >= 1
        assert len(sdet_result["recommendations"]) > 0

        print("✓ Fullstack → SDET workflow completed successfully")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
