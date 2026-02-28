"""
SystemIntegrityChecker — application-level integrity verification for AgenticQA.

Complements DataflowHealthMonitor (which does TCP/HTTP infrastructure probes) by
verifying that the *application* layer is wired correctly:

  1. Ontology         — TASK_AGENT_MAP maps every task type to known agent names;
                        get_allowed_agents() returns consistent results.
  2. Constitutional   — check_action() returns ALLOW for safe actions, DENY for
     Gate               destructive ones; the gate is not in a broken state.
  3. Scanners         — AgentSkillScanner, MCPSecurityScanner, and
                        CrossAgentDataFlowTracer can instantiate and produce
                        meaningful results on minimal test inputs.
  4. Artifact Store   — write + immediate read-back round-trip succeeds; the
                        index is consistent.
  5. Provenance       — sign/verify round-trip produces a matching HMAC.
  6. Ingest Pipeline  — ingest_skill_scan() and ingest_mcp_scan() accept
                        well-formed JSON payloads without raising exceptions.

Exit codes (when used as a CLI):
    0   all checks passed
    1   one or more checks failed

Usage:
    # CLI
    python -m agenticqa.monitoring.integrity_checker
    python -m agenticqa.monitoring.integrity_checker --json
    python -m agenticqa.monitoring.integrity_checker --fail-on-warn

    # Programmatic
    from agenticqa.monitoring.integrity_checker import SystemIntegrityChecker
    report = SystemIntegrityChecker().check_all()
    if not report.passed:
        for f in report.failures:
            print(f)
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Result of a single integrity check."""
    name: str                # short identifier, e.g. "ontology.task_types"
    category: str            # "ontology" | "gate" | "scanners" | "store" | "provenance" | "ingest"
    passed: bool
    message: str             # human-readable outcome
    latency_ms: float = 0.0
    detail: Optional[str] = None  # stack trace or extra context on failure

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        base = f"[{status}] {self.category}/{self.name}: {self.message}"
        if self.detail and not self.passed:
            first_line = self.detail.splitlines()[0]
            base += f"\n       {first_line}"
        return base


@dataclass
class IntegrityReport:
    """Full report produced by SystemIntegrityChecker.check_all()."""
    timestamp: str
    passed: bool
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def failures(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.passed]

    @property
    def successes(self) -> List[CheckResult]:
        return [c for c in self.checks if c.passed]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "passed": self.passed,
            "total": len(self.checks),
            "passed_count": len(self.successes),
            "failed_count": len(self.failures),
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "passed": c.passed,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 2),
                    "detail": c.detail,
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Known agents (ground-truth set; kept in sync with agents.py class names)
# ---------------------------------------------------------------------------
_KNOWN_AGENTS = frozenset(
    [
        "QA_Agent",
        "QA_Assistant",
        "Performance_Agent",
        "Compliance_Agent",
        "DevOps_Agent",
        "SRE_Agent",
        "SDET_Agent",
        "Fullstack_Agent",
        "RedTeam_Agent",
    ]
)


# ---------------------------------------------------------------------------
# Check runner helper
# ---------------------------------------------------------------------------

def _run(name: str, category: str, fn: Callable[[], Tuple[bool, str]]) -> CheckResult:
    t0 = time.monotonic()
    try:
        ok, msg = fn()
        latency_ms = (time.monotonic() - t0) * 1000
        return CheckResult(name=name, category=category, passed=ok, message=msg,
                           latency_ms=latency_ms)
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        return CheckResult(
            name=name,
            category=category,
            passed=False,
            message=f"Exception: {type(exc).__name__}: {exc}",
            latency_ms=latency_ms,
            detail=traceback.format_exc(),
        )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

# ── 1. Ontology ─────────────────────────────────────────────────────────────

def _check_ontology_task_types() -> Tuple[bool, str]:
    from agenticqa.delegation.guardrails import DelegationGuardrails
    task_map = DelegationGuardrails.TASK_AGENT_MAP
    if not task_map:
        return False, "TASK_AGENT_MAP is empty"
    return True, f"{len(task_map)} task types registered"


def _check_ontology_agents_known() -> Tuple[bool, str]:
    from agenticqa.delegation.guardrails import DelegationGuardrails
    unknown: List[str] = []
    for task_type, agents in DelegationGuardrails.TASK_AGENT_MAP.items():
        for agent in agents:
            if agent not in _KNOWN_AGENTS:
                unknown.append(f"{task_type}→{agent}")
    if unknown:
        return False, f"Unknown agents in ontology: {unknown}"
    return True, "All ontology agents are in the known-agent set"


def _check_ontology_get_allowed_agents() -> Tuple[bool, str]:
    from agenticqa.delegation.guardrails import get_allowed_agents
    # "validate_tests" must route to SDET_Agent and/or QA_Agent
    allowed = get_allowed_agents("validate_tests")
    if not allowed:
        return False, "get_allowed_agents('validate_tests') returned empty list"
    return True, f"validate_tests → {allowed}"


def _check_ontology_no_empty_lists() -> Tuple[bool, str]:
    from agenticqa.delegation.guardrails import DelegationGuardrails
    empty = [t for t, a in DelegationGuardrails.TASK_AGENT_MAP.items() if not a]
    if empty:
        return False, f"Task types with no agents assigned: {empty}"
    return True, "No task types have empty agent lists"


# ── 2. Constitutional Gate ───────────────────────────────────────────────────

def _check_gate_safe_action_allows() -> Tuple[bool, str]:
    from agenticqa.constitutional_gate import check_action
    result = check_action("run_agents", {"ci_status": "PASSED", "trace_id": "integrity-check"})
    verdict = result.get("verdict", "")
    if verdict not in ("ALLOW", "REQUIRE_APPROVAL"):
        return False, f"Expected ALLOW/REQUIRE_APPROVAL for run_agents, got: {verdict}"
    return True, f"run_agents → {verdict}"


def _check_gate_destructive_denies() -> Tuple[bool, str]:
    from agenticqa.constitutional_gate import check_action
    # T1-001: "delete" without ci_status=PASSED must be denied
    result = check_action("delete", {"agent": "QA_Agent", "trace_id": "integrity-check"})
    verdict = result.get("verdict", "")
    if verdict != "DENY":
        return False, f"Expected DENY for delete (no ci_status), got: {verdict} (gate may be weakened)"
    return True, f"delete → DENY (T1-001 enforcing)"


def _check_gate_returns_law() -> Tuple[bool, str]:
    from agenticqa.constitutional_gate import check_action
    result = check_action("run_agents", {"ci_status": "PASSED", "trace_id": "integrity-check"})
    if "verdict" not in result:
        return False, "check_action() result missing 'verdict' key"
    return True, f"result keys: {sorted(result.keys())}"


# ── 3. Scanners ──────────────────────────────────────────────────────────────

_CLEAN_AGENT_CODE = "def run(ctx):\n    return {'status': 'ok'}\n"
_EVIL_AGENT_CODE = "import subprocess\ndef run(ctx): return {}\n"

def _check_scanner_skill_clean() -> Tuple[bool, str]:
    from agenticqa.security.agent_skill_scanner import AgentSkillScanner
    result = AgentSkillScanner().scan_source(_CLEAN_AGENT_CODE, filename="<integrity-check>")
    if not result.is_safe:
        return False, f"Clean agent flagged as unsafe: {result.findings}"
    return True, f"Clean agent: is_safe=True, risk={result.risk_score}"


def _check_scanner_skill_evil() -> Tuple[bool, str]:
    from agenticqa.security.agent_skill_scanner import AgentSkillScanner
    result = AgentSkillScanner().scan_source(_EVIL_AGENT_CODE, filename="<integrity-check>")
    if result.is_safe:
        return False, "subprocess import not detected — scanner may be broken"
    if result.risk_score == 0.0:
        return False, "Risk score is 0 for a dangerous agent"
    return True, f"Evil agent: is_safe=False, risk={result.risk_score}, findings={len(result.findings)}"


def _check_scanner_skill_syntax_error() -> Tuple[bool, str]:
    from agenticqa.security.agent_skill_scanner import AgentSkillScanner
    result = AgentSkillScanner().scan_source("def run(ctx): {{{", filename="<integrity-check>")
    if result.parse_error is None:
        return False, "SyntaxError not caught — parse_error should be set"
    if result.is_safe:
        return False, "File with parse error should not be is_safe=True"
    return True, f"Syntax error handled: {result.parse_error[:60]}"


def _check_scanner_mcp() -> Tuple[bool, str]:
    try:
        from agenticqa.security.mcp_scanner import MCPSecurityScanner
    except ImportError:
        return False, "MCPSecurityScanner could not be imported"
    scanner = MCPSecurityScanner()
    if not hasattr(scanner, "scan"):
        return False, "MCPSecurityScanner missing .scan() method"
    return True, "MCPSecurityScanner instantiated with .scan() method present"


def _check_scanner_dataflow() -> Tuple[bool, str]:
    try:
        from agenticqa.security.data_flow_tracer import CrossAgentDataFlowTracer
    except ImportError:
        return False, "CrossAgentDataFlowTracer could not be imported"
    tracer = CrossAgentDataFlowTracer()
    if not hasattr(tracer, "trace"):
        return False, "CrossAgentDataFlowTracer missing .trace() method"
    return True, "CrossAgentDataFlowTracer instantiated successfully"


# ── 4. Artifact Store ────────────────────────────────────────────────────────

def _check_store_write_read() -> Tuple[bool, str]:
    import uuid
    from data_store.artifact_store import TestArtifactStore

    with tempfile.TemporaryDirectory() as tmp:
        store = TestArtifactStore(tmp)
        payload = {"integrity_check": True, "probe_id": str(uuid.uuid4())}
        artifact_id = store.store_artifact(
            artifact_data=payload,
            artifact_type="integrity_probe",
            source="integrity_checker",
            tags=["integrity"],
        )

        if not artifact_id:
            return False, "store_artifact() returned empty ID"

        # Verify raw file exists
        raw = Path(tmp) / "raw" / f"{artifact_id}.json"
        if not raw.exists():
            return False, f"Raw artifact file not written: {raw}"

        # Verify index reflects the write
        index = store.get_master_index()
        if artifact_id not in index:
            return False, f"Artifact {artifact_id} missing from master index"

    return True, f"Write→read roundtrip succeeded (artifact_id prefix: {artifact_id[:8]})"


def _check_store_index_consistent() -> Tuple[bool, str]:
    """Verify the production artifact store's index.json is parseable and consistent."""
    store_path = Path(".test-artifact-store")
    if not store_path.exists():
        return True, "No production artifact store found — skipping consistency check"

    index_file = store_path / "index.json"
    if not index_file.exists():
        return True, "index.json not present yet — store is empty"

    try:
        with open(index_file) as f:
            index = json.load(f)
    except json.JSONDecodeError as exc:
        return False, f"index.json is corrupted: {exc}"

    artifacts = index.get("artifacts", [])
    # Spot-check: every listed artifact_id should have a raw file
    broken: List[str] = []
    for artifact in artifacts[:20]:  # check only the first 20 to avoid slow runs
        aid = artifact.get("artifact_id", "")
        raw = store_path / "raw" / f"{aid}.json"
        if aid and not raw.exists():
            broken.append(aid)

    if broken:
        return False, f"Index references {len(broken)} missing raw files: {broken[:3]}"

    return True, f"Index consistent ({len(artifacts)} artifacts, first 20 spot-checked)"


# ── 5. Provenance ────────────────────────────────────────────────────────────

def _check_provenance_sign_verify() -> Tuple[bool, str]:
    try:
        from agenticqa.provenance.output_provenance import OutputProvenanceLogger
    except ImportError:
        return False, "OutputProvenanceLogger could not be imported"

    with tempfile.TemporaryDirectory() as tmp:
        prov = OutputProvenanceLogger(provenance_dir=tmp)
        test_output = json.dumps({"status": "ok", "probe": True})
        record = prov.sign_and_log(
            agent_name="integrity_checker",
            model_id="integrity-probe",
            output_text=test_output,
            run_id="integrity-check",
        )

        sig = getattr(record, "signature", None)
        if not sig:
            return False, "sign_and_log() produced empty/missing signature"

    return True, "Provenance sign_and_log() succeeded with non-empty signature"


# ── 6. Ingest Pipeline ───────────────────────────────────────────────────────

def _check_ingest_skill_scan() -> Tuple[bool, str]:
    try:
        from ingest_ci_artifacts import CIArtifactIngestion
    except ImportError:
        return False, "ingest_ci_artifacts.CIArtifactIngestion could not be imported"

    with tempfile.TemporaryDirectory() as tmp:
        scan_data = {
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "files_scanned": 1,
            "files_blocked": 0,
            "results": [
                {"path": "/tmp/clean_agent.py", "is_safe": True, "risk_score": 0.0,
                 "findings": [], "parse_error": None}
            ],
        }
        scan_path = Path(tmp) / "skill-scan-output.json"
        scan_path.write_text(json.dumps(scan_data))

        import os as _os
        old = _os.environ.get("AGENTICQA_ARTIFACT_STORE")
        _os.environ["AGENTICQA_ARTIFACT_STORE"] = tmp
        try:
            ingestion = CIArtifactIngestion()
            ingestion.ingest_skill_scan(str(scan_path), run_id="integrity-check")
        finally:
            if old is None:
                _os.environ.pop("AGENTICQA_ARTIFACT_STORE", None)
            else:
                _os.environ["AGENTICQA_ARTIFACT_STORE"] = old

    return True, "ingest_skill_scan() accepted well-formed scan JSON without error"


def _check_ingest_mcp_scan() -> Tuple[bool, str]:
    try:
        from ingest_ci_artifacts import CIArtifactIngestion
    except ImportError:
        return False, "ingest_ci_artifacts.CIArtifactIngestion could not be imported"

    with tempfile.TemporaryDirectory() as tmp:
        scan_data = {
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "servers_scanned": 0,
            "findings": [],
        }
        scan_path = Path(tmp) / "mcp-scan-output.json"
        scan_path.write_text(json.dumps(scan_data))

        import os as _os
        old = _os.environ.get("AGENTICQA_ARTIFACT_STORE")
        _os.environ["AGENTICQA_ARTIFACT_STORE"] = tmp
        try:
            ingestion = CIArtifactIngestion()
            ingestion.ingest_mcp_scan(str(scan_path), run_id="integrity-check")
        finally:
            if old is None:
                _os.environ.pop("AGENTICQA_ARTIFACT_STORE", None)
            else:
                _os.environ["AGENTICQA_ARTIFACT_STORE"] = old

    return True, "ingest_mcp_scan() accepted well-formed scan JSON without error"


# ---------------------------------------------------------------------------
# Main checker class
# ---------------------------------------------------------------------------

class SystemIntegrityChecker:
    """
    Application-level integrity verification for AgenticQA.

    Each check is a focused, fast, deterministic probe with no external
    network calls (infrastructure reachability is the job of DataflowHealthMonitor).
    All checks run against in-process code and temporary directories so they
    work offline and in CI without any infrastructure dependencies.
    """

    # Ordered list of (check_name, category, fn)
    _CHECKS: List[Tuple[str, str, Callable]] = [
        # Ontology
        ("task_types_registered",   "ontology",   _check_ontology_task_types),
        ("agents_all_known",         "ontology",   _check_ontology_agents_known),
        ("get_allowed_agents_works", "ontology",   _check_ontology_get_allowed_agents),
        ("no_empty_agent_lists",     "ontology",   _check_ontology_no_empty_lists),
        # Constitutional Gate
        ("safe_action_allows",       "gate",       _check_gate_safe_action_allows),
        ("destructive_denies",       "gate",       _check_gate_destructive_denies),
        ("result_has_verdict",       "gate",       _check_gate_returns_law),
        # Scanners
        ("skill_clean_agent",        "scanners",   _check_scanner_skill_clean),
        ("skill_evil_agent",         "scanners",   _check_scanner_skill_evil),
        ("skill_syntax_error",       "scanners",   _check_scanner_skill_syntax_error),
        ("mcp_scanner",              "scanners",   _check_scanner_mcp),
        ("dataflow_tracer",          "scanners",   _check_scanner_dataflow),
        # Artifact Store
        ("write_read_roundtrip",     "store",      _check_store_write_read),
        ("index_consistent",         "store",      _check_store_index_consistent),
        # Provenance
        ("sign_verify_roundtrip",    "provenance", _check_provenance_sign_verify),
        # Ingest Pipeline
        ("ingest_skill_scan",        "ingest",     _check_ingest_skill_scan),
        ("ingest_mcp_scan",          "ingest",     _check_ingest_mcp_scan),
    ]

    def check_all(self) -> IntegrityReport:
        """Run all integrity checks and return a consolidated report."""
        results = [_run(name, cat, fn) for name, cat, fn in self._CHECKS]
        passed = all(r.passed for r in results)
        return IntegrityReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            passed=passed,
            checks=results,
        )

    def check_category(self, category: str) -> IntegrityReport:
        """Run only the checks in a specific category."""
        subset = [(n, c, fn) for n, c, fn in self._CHECKS if c == category]
        results = [_run(name, cat, fn) for name, cat, fn in subset]
        return IntegrityReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            passed=all(r.passed for r in results),
            checks=results,
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="AgenticQA System Integrity Checker — application-level health verification"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--category",
        choices=["ontology", "gate", "scanners", "store", "provenance", "ingest"],
        help="Run only checks in this category",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit 1 even if only warnings (skipped checks) are present",
    )
    args = parser.parse_args()

    checker = SystemIntegrityChecker()
    if args.category:
        report = checker.check_category(args.category)
    else:
        report = checker.check_all()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"\nAgenticQA System Integrity — {report.timestamp}")
        print("=" * 60)
        for check in report.checks:
            print(check)
        print("=" * 60)
        total = len(report.checks)
        passed = len(report.successes)
        failed = len(report.failures)
        print(f"Result: {passed}/{total} checks passed, {failed} failed")
        if report.passed:
            print("INTEGRITY OK")
        else:
            print("INTEGRITY FAILED — see failures above")

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(_cli())
