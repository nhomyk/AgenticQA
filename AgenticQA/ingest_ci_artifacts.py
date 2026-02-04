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
            self.rag.store_execution_result("compliance", document)
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

            self.rag.store_execution_result("qa", document)
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

            self.rag.store_execution_result("qa", document)
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

            self.rag.store_execution_result("devops", document)
            self.ingested_count += 1

            print(f"  ✅ Ingested security audit")
            return True

        except Exception as e:
            print(f"  ❌ Failed to ingest security audit: {e}")
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
    parser.add_argument('--pa11y-report', help='Path to Pa11y report')
    parser.add_argument('--test-results', help='Path to test results JSON')
    parser.add_argument('--coverage', help='Path to coverage report JSON')
    parser.add_argument('--security-audit', help='Path to security audit JSON')
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

        if args.test_results:
            ingestion.ingest_test_results(args.test_results, args.test_framework, args.run_id)

        if args.coverage:
            ingestion.ingest_coverage_report(args.coverage, args.run_id)

        if args.security_audit:
            ingestion.ingest_security_scan(args.security_audit, args.run_id)

    print(f"\n✅ Total artifacts ingested: {ingestion.ingested_count}")
    print("\n💡 Agents will now learn from these artifacts in future runs!")
    print("   - ComplianceAgent: Accessibility patterns")
    print("   - QA/SDET Agents: Test failure patterns")
    print("   - DevOps Agent: Security vulnerabilities")

    return 0


if __name__ == "__main__":
    sys.exit(main())
