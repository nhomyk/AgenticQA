#!/usr/bin/env python3
"""
CI Artifact Ingestion Script

Ingests CI artifacts (Pa11y reports, test results, coverage, etc.) into Weaviate
for RAG learning. This creates the learning loop that allows agents to improve
over time.

Usage:
    python ingest_ci_artifacts.py --artifact-dir ./artifacts
    python ingest_ci_artifacts.py --pa11y-report pa11y-report.txt
    python ingest_ci_artifacts.py --test-results test-results.json

This should be called at the end of every CI run to enable continuous learning.
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


class CIArtifactIngestion:
    """Ingests CI artifacts into Weaviate for agent learning"""

    def __init__(self):
        self.ingested_count = 0
        self.rag = None
        self._initialize_rag()

    def _initialize_rag(self):
        """Initialize RAG system"""
        try:
            from src.agenticqa.rag.config import create_rag_system
            self.rag = create_rag_system()
            print("✅ Connected to Weaviate")
        except Exception as e:
            print(f"⚠️  RAG initialization failed: {e}")
            print("   Artifacts will not be ingested. Enable Weaviate for learning.")
            self.rag = None

    def close(self):
        """Close Weaviate connection"""
        if self.rag and hasattr(self.rag, 'vector_store'):
            try:
                self.rag.vector_store.close()
            except Exception:
                pass

    def ingest_pa11y_report(self, report_path: str, run_id: str = None) -> bool:
        """
        Ingest Pa11y accessibility report into Weaviate.

        Stores:
        - Violation types and counts
        - URLs scanned
        - Error patterns
        - Recommended fixes

        This enables the ComplianceAgent to learn from past accessibility issues.
        """
        if not self.rag:
            return False

        try:
            with open(report_path, 'r') as f:
                content = f.read()

            # Parse report
            violations = self._parse_pa11y_violations(content)

            # Create structured document for Weaviate
            document = {
                "artifact_type": "pa11y_report",
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id or "unknown",
                "violation_count": len(violations),
                "violations": violations,
                "raw_content": content[:5000],  # Truncate for storage
                "agent_type": "compliance",
                "tags": ["accessibility", "wcag", "pa11y"]
            }

            # Store in Weaviate
            self.rag.log_agent_execution("compliance", document)
            self.ingested_count += 1

            print(f"  ✅ Ingested Pa11y report: {len(violations)} violations")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest Pa11y report: {e}")
            return False

    def ingest_test_results(self, results_path: str, test_framework: str, run_id: str = None) -> bool:
        """
        Ingest test results (Jest, Playwright, Cypress, etc.) into Weaviate.

        Stores:
        - Test names and status
        - Failure patterns
        - Execution times
        - Error messages

        This enables SDET/QA agents to learn from test failures.
        """
        if not self.rag:
            return False

        try:
            with open(results_path, 'r') as f:
                if results_path.endswith('.json'):
                    results = json.load(f)
                else:
                    results = {"raw": f.read()}

            document = {
                "artifact_type": "test_results",
                "test_framework": test_framework,
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id or "unknown",
                "results": results,
                "agent_type": "qa",
                "tags": ["testing", test_framework, "results"]
            }

            self.rag.log_agent_execution("qa", document)
            self.ingested_count += 1

            print(f"  ✅ Ingested {test_framework} test results")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest test results: {e}")
            return False

    def ingest_coverage_report(self, coverage_path: str, run_id: str = None) -> bool:
        """
        Ingest code coverage report into Weaviate.

        Stores:
        - Coverage percentages
        - Uncovered files
        - Coverage trends

        This enables SDET agent to identify testing gaps.
        """
        if not self.rag:
            return False

        try:
            with open(coverage_path, 'r') as f:
                coverage = json.load(f)

            document = {
                "artifact_type": "coverage_report",
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id or "unknown",
                "coverage_data": coverage,
                "agent_type": "qa",
                "tags": ["coverage", "testing", "sdet"]
            }

            self.rag.log_agent_execution("qa", document)
            self.ingested_count += 1

            print(f"  ✅ Ingested coverage report")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest coverage report: {e}")
            return False

    def ingest_security_scan(self, audit_path: str, run_id: str = None) -> bool:
        """
        Ingest security audit results (npm audit, etc.) into Weaviate.

        Stores:
        - Vulnerabilities found
        - Severity levels
        - Affected packages
        - Remediation suggestions

        This enables DevOps agent to learn from security patterns.
        """
        if not self.rag:
            return False

        try:
            with open(audit_path, 'r') as f:
                audit = json.load(f)

            document = {
                "artifact_type": "security_audit",
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id or "unknown",
                "audit_data": audit,
                "agent_type": "devops",
                "tags": ["security", "audit", "npm"]
            }

            self.rag.log_agent_execution("devops", document)
            self.ingested_count += 1

            print(f"  ✅ Ingested security audit")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest security audit: {e}")
            return False

    def ingest_pa11y_json(self, json_path: str, run_id: str = None) -> bool:
        """
        Ingest Pa11y JSON report (structured data).

        Stores:
        - Timestamp
        - Error count
        - Status
        - URL scanned
        """
        if not self.rag:
            return False

        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            # Create document for Weaviate
            document = {
                "artifact_type": "pa11y_json",
                "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
                "run_id": run_id or "unknown",
                "error_count": data.get("errorCount", 0),
                "status": data.get("status", "unknown"),
                "url": data.get("url", ""),
                "agent_type": "compliance",
                "tags": ["accessibility", "pa11y", "structured"]
            }

            # If this is a revalidation report
            if "errorCountBefore" in data:
                document["error_count_before"] = data.get("errorCountBefore")
                document["error_count_after"] = data.get("errorCountAfter")
                document["errors_fixed"] = data.get("errorsFixed")
                document["artifact_type"] = "pa11y_revalidation"

            self.rag.log_agent_execution("compliance", document)
            self.ingested_count += 1

            print(f"  ✅ Ingested Pa11y JSON: {document['error_count']} errors")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest Pa11y JSON: {e}")
            return False

    def ingest_agent_log(self, log_path: str, agent_type: str, run_id: str = None) -> bool:
        """
        Ingest agent execution log (e.g., autofix-output.txt).

        Stores:
        - Agent decisions
        - Fixes applied
        - Success/failure messages
        - Execution context
        """
        if not self.rag:
            return False

        try:
            with open(log_path, 'r') as f:
                content = f.read()

            # Parse log for key information
            fixes_applied = content.count("Fixes Applied")
            errors_found = content.count("Error:")
            warnings_found = content.count("Warning:")

            document = {
                "artifact_type": "agent_execution_log",
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id or "unknown",
                "agent_type": agent_type,
                "fixes_applied": fixes_applied,
                "errors": errors_found,
                "warnings": warnings_found,
                "log_content": content[:10000],  # Truncate for storage
                "tags": [agent_type, "execution", "log"]
            }

            self.rag.log_agent_execution(agent_type, document)
            self.ingested_count += 1

            print(f"  ✅ Ingested {agent_type} agent log: {fixes_applied} fixes")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest agent log: {e}")
            return False

    def ingest_test_failures(self, failures_dir: str, run_id: str = None) -> bool:
        """
        Ingest test failure details from test-failures/ directory.

        Stores:
        - Extracted error messages
        - Failure patterns
        - Framework-specific failures
        """
        if not self.rag:
            return False

        failures_path = Path(failures_dir)
        if not failures_path.exists():
            print(f"  ⚠️  Test failures directory not found: {failures_dir}")
            return False

        try:
            failures_ingested = 0

            for failure_file in failures_path.glob('*.txt'):
                with open(failure_file, 'r') as f:
                    content = f.read()

                if not content.strip():
                    continue

                # Extract framework from filename (e.g., jest-errors.txt → jest)
                framework = failure_file.stem.replace('-errors', '')

                document = {
                    "artifact_type": "test_failure",
                    "timestamp": datetime.utcnow().isoformat(),
                    "run_id": run_id or "unknown",
                    "framework": framework,
                    "error_count": content.count('\n'),
                    "errors": content[:5000],  # Truncate for storage
                    "agent_type": "qa",
                    "tags": ["test", "failure", framework]
                }

                self.rag.log_agent_execution("qa", document)
                failures_ingested += 1

            self.ingested_count += failures_ingested
            print(f"  ✅ Ingested {failures_ingested} test failure files")
            return failures_ingested > 0

        except Exception as e:
            print(f"  ❌ Failed to ingest test failures: {e}")
            return False

    def ingest_pipeline_health(self, health_log: str, run_id: str = None) -> bool:
        """
        Ingest pipeline health check results.

        Stores:
        - Test results
        - System health metrics
        - Critical failures
        """
        if not self.rag:
            return False

        try:
            with open(health_log, 'r') as f:
                content = f.read()

            # Parse health metrics
            passed_count = content.count("passed")
            failed_count = content.count("failed")
            warnings_count = content.count("warning")

            document = {
                "artifact_type": "pipeline_health",
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id or "unknown",
                "tests_passed": passed_count,
                "tests_failed": failed_count,
                "warnings": warnings_count,
                "log_content": content[:10000],
                "agent_type": "sre",
                "tags": ["pipeline", "health", "validation"]
            }

            self.rag.log_agent_execution("sre", document)
            self.ingested_count += 1

            print(f"  ✅ Ingested pipeline health: {passed_count} passed, {failed_count} failed")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest pipeline health: {e}")
            return False

    def ingest_directory(self, artifact_dir: str, run_id: str = None) -> Dict[str, int]:
        """
        Ingest all artifacts from a directory.

        Automatically detects artifact types and ingests them.
        """
        artifact_dir = Path(artifact_dir)
        stats = {
            "pa11y": 0,
            "tests": 0,
            "coverage": 0,
            "security": 0,
            "other": 0
        }

        if not artifact_dir.exists():
            print(f"❌ Directory not found: {artifact_dir}")
            return stats

        print(f"📦 Scanning {artifact_dir} for artifacts...")

        for file_path in artifact_dir.rglob('*'):
            if not file_path.is_file():
                continue

            filename = file_path.name.lower()

            # Pa11y reports
            if 'pa11y' in filename:
                if self.ingest_pa11y_report(str(file_path), run_id):
                    stats["pa11y"] += 1

            # Test results
            elif any(fw in filename for fw in ['jest', 'playwright', 'cypress', 'vitest']):
                framework = next((fw for fw in ['jest', 'playwright', 'cypress', 'vitest'] if fw in filename), 'unknown')
                if self.ingest_test_results(str(file_path), framework, run_id):
                    stats["tests"] += 1

            # Coverage
            elif 'coverage' in filename and filename.endswith('.json'):
                if self.ingest_coverage_report(str(file_path), run_id):
                    stats["coverage"] += 1

            # Security
            elif 'audit' in filename and filename.endswith('.json'):
                if self.ingest_security_scan(str(file_path), run_id):
                    stats["security"] += 1

            else:
                stats["other"] += 1

        return stats

    def _parse_pa11y_violations(self, content: str) -> List[Dict]:
        """Parse Pa11y report and extract violations"""
        import re
        violations = []

        # Parse error lines (• prefix)
        error_lines = re.findall(r'^\s*•\s*(.+)$', content, re.MULTILINE)

        for error_text in error_lines:
            violations.append({
                "message": error_text.strip(),
                "type": self._classify_violation(error_text)
            })

        return violations

    def _classify_violation(self, error_text: str) -> str:
        """Classify violation type from error message"""
        if 'contrast' in error_text.lower():
            return 'color_contrast'
        elif 'label' in error_text.lower() or 'name available' in error_text.lower():
            return 'missing_label'
        elif 'alt' in error_text.lower():
            return 'missing_alt'
        elif 'aria' in error_text.lower():
            return 'aria_issue'
        else:
            return 'other'


def main():
    parser = argparse.ArgumentParser(description='Ingest CI artifacts into Weaviate for agent learning')
    parser.add_argument('--artifact-dir', help='Directory containing artifacts')
    parser.add_argument('--pa11y-report', help='Path to Pa11y report (text)')
    parser.add_argument('--pa11y-json', help='Path to Pa11y JSON report')
    parser.add_argument('--test-results', help='Path to test results JSON')
    parser.add_argument('--coverage', help='Path to coverage report JSON')
    parser.add_argument('--security-audit', help='Path to security audit JSON')
    parser.add_argument('--agent-log', help='Path to agent execution log')
    parser.add_argument('--agent-type', help='Agent type (for --agent-log)', default='unknown')
    parser.add_argument('--test-failures', help='Path to test-failures directory')
    parser.add_argument('--pipeline-health', help='Path to pipeline health log')
    parser.add_argument('--run-id', help='CI run ID for tracking', default=os.getenv('GITHUB_RUN_ID', 'local'))
    parser.add_argument('--test-framework', help='Test framework name (for --test-results)', default='unknown')

    args = parser.parse_args()

    print("🧠 CI Artifact Ingestion - Weaviate Learning System")
    print("=" * 60)

    ingestion = CIArtifactIngestion()

    if not ingestion.rag:
        print("\n❌ Weaviate not available. Artifacts will not be ingested.")
        print("   Configure Weaviate connection to enable learning.")
        return 1

    # Ingest based on provided arguments
    if args.artifact_dir:
        stats = ingestion.ingest_directory(args.artifact_dir, args.run_id)
        print("\n📊 Ingestion Summary:")
        print(f"  Pa11y Reports: {stats['pa11y']}")
        print(f"  Test Results: {stats['tests']}")
        print(f"  Coverage Reports: {stats['coverage']}")
        print(f"  Security Audits: {stats['security']}")
        print(f"  Other Files: {stats['other']}")

    else:
        # Ingest individual files
        if args.pa11y_report:
            ingestion.ingest_pa11y_report(args.pa11y_report, args.run_id)

        if args.pa11y_json:
            ingestion.ingest_pa11y_json(args.pa11y_json, args.run_id)

        if args.test_results:
            ingestion.ingest_test_results(args.test_results, args.test_framework, args.run_id)

        if args.coverage:
            ingestion.ingest_coverage_report(args.coverage, args.run_id)

        if args.security_audit:
            ingestion.ingest_security_scan(args.security_audit, args.run_id)

        if args.agent_log:
            ingestion.ingest_agent_log(args.agent_log, args.agent_type, args.run_id)

        if args.test_failures:
            ingestion.ingest_test_failures(args.test_failures, args.run_id)

        if args.pipeline_health:
            ingestion.ingest_pipeline_health(args.pipeline_health, args.run_id)

    print(f"\n✅ Total artifacts ingested: {ingestion.ingested_count}")
    print("\n💡 Agents will now learn from these artifacts in future runs!")
    print("   - ComplianceAgent: Accessibility patterns & auto-fix logs")
    print("   - QA/SDET Agents: Test results & failure patterns")
    print("   - DevOps Agent: Security vulnerabilities")
    print("   - SRE Agent: Pipeline health metrics")

    # Clean up
    ingestion.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
