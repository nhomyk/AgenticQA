#!/usr/bin/env python3
"""CI step: run pip-audit CVE scan and record compliance drift snapshot."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.compliance.drift_detector import ComplianceDriftDetector
from agenticqa.security.cve_reachability import CVEReachabilityAnalyzer

run_id = os.getenv("GITHUB_RUN_ID", "local")
repo_path = os.getenv("GITHUB_WORKSPACE", ".")

reach = CVEReachabilityAnalyzer().scan_python(repo_path)
violations = [
    {"type": "reachable_cve", "package": c.package, "cve_id": c.cve_id}
    for c in reach.reachable_cves
]

detector = ComplianceDriftDetector()
detector.record_run(run_id, violations, repo_path=repo_path)
drift = detector.detect_drift(repo_path)

result = {
    "drift": drift,
    "reachable_cves": len(reach.reachable_cves),
    "scan_error": reach.scan_error,
}
print(json.dumps(result, indent=2))

if drift["direction"] == "worsening":
    print(f"WARNING: compliance worsened by {drift['delta']} violations", file=sys.stderr)
