"""
SARIF 2.1.0 exporter for AgenticQA findings.

Converts SRE, Compliance, CVE Reachability, and Red Team results into
SARIF (Static Analysis Results Interchange Format) for upload to
GitHub Code Scanning via github/codeql-action/upload-sarif.

Usage:
    # CLI — produce sarif from latest agent outputs:
    python -m agenticqa.export.sarif --sre sre-output.json --out results.sarif

    # Programmatic:
    from agenticqa.export.sarif import SARIFExporter
    sarif = SARIFExporter()
    sarif.add_sre_result(sre_result, repo_path=".")
    sarif.add_compliance_result(compliance_result)
    sarif.write("results.sarif")
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
_VERSION = "2.1.0"
_TOOL_NAME = "AgenticQA"
_TOOL_VERSION = "1.0.0"
_TOOL_URI = "https://github.com/nhomyk/AgenticQA"

# Map linting rule codes to SARIF security-severity (for GitHub UI colouring)
_SECURITY_SEVERITY: Dict[str, str] = {
    # Shell injection risks
    "SC2086": "5.0",  # unquoted variable — potential word splitting
    "SC2046": "5.0",  # unquoted command substitution
    "SC2006": "3.0",  # backtick in shell
    # Python security-adjacent
    "B101": "5.0",    # bandit: assert used
    "B102": "7.0",    # bandit: exec used
    "B104": "8.0",    # bandit: bind all interfaces
    "B105": "7.0",    # bandit: hardcoded password string
    "B106": "7.0",    # bandit: hardcoded password function arg
    "B107": "7.0",    # bandit: hardcoded password default
    "B108": "4.0",    # bandit: predictable temp file
    "B110": "3.0",    # bandit: try-except-pass
    "B324": "9.0",    # bandit: md5 / sha1
    "B601": "9.5",    # bandit: paramiko shell=True
    "B602": "9.5",    # bandit: subprocess shell=True
    "B603": "7.5",    # bandit: subprocess without shell=True
    "B607": "6.0",    # bandit: start process with partial path
    "reachable_cve": "9.0",
    # Legal risk scanner
    "CREDENTIAL_EXPOSURE": "9.5",
    "PRIVILEGE_BREACH":    "8.5",
    "PII_DOCUMENT_PUBLIC": "8.0",
    "GDPR_VIOLATION":      "7.5",
    "NO_AUTH_ROUTE":       "7.0",
    "SSRF_RISK":           "6.0",
    # Prompt injection scanner
    "PROMPT_INJECTION_SURFACE": "9.5",
    "SYSTEM_PROMPT_OVERRIDE":   "9.0",
    "TEMPLATE_INJECTION":       "8.0",
    "UNVALIDATED_LLM_OUTPUT":   "7.0",
    # HIPAA PHI scanner
    "PHI_HARDCODED":       "9.5",
    "PHI_TO_LLM":          "9.0",
    "PHI_DOCUMENT_PUBLIC": "9.0",
    "PHI_IN_LOGS":         "8.0",
    "HIPAA_AUDIT_MISSING": "7.5",
    # AI Output Provenance
    "UNATTESTED_OUTPUT": "8.5",
    # EU AI Act compliance
    "AI_ACT_Art_9":  "8.0",
    "AI_ACT_Art_13": "7.0",
    "AI_ACT_Art_14": "7.5",
    "AI_ACT_Art_22": "9.0",
    # MCP Security scanner
    "MCP_TOOL_POISONING":       "9.5",
    "MCP_SSRF":                 "8.5",
    "MCP_SUPPLY_CHAIN":         "9.0",
    "MCP_CREDENTIAL_EXFIL":     "9.5",
    "MCP_UNSAFE_DESERIALIZATION": "8.0",
    "MCP_PROMPT_INJECTION":     "9.0",
    # Cross-agent DataFlow tracer
    "TAINT_PROPAGATION":        "7.5",
    "UNSANITIZED_SINK":         "8.5",
    "CROSS_AGENT_DATA_LEAK":    "9.0",
    "UNVALIDATED_INPUT_FLOW":   "7.0",
}

_LEVEL_MAP = {
    "error": "error",
    "warning": "warning",
    "note": "note",
    "info": "note",
    # flake8 / pyflakes
    "F": "warning",
    "E": "note",
    "W": "warning",
    # shellcheck
    "SC": "warning",
    # bandit
    "B": "warning",
}


def _rule_level(rule_id: str, severity: str = "") -> str:
    if severity in ("error", "warning", "note"):
        return severity
    for prefix, level in _LEVEL_MAP.items():
        if rule_id.startswith(prefix):
            return level
    return "warning"


def _make_rule(rule_id: str, description: str = "", help_uri: str = "") -> Dict:
    r: Dict[str, Any] = {
        "id": rule_id,
        "shortDescription": {"text": description or rule_id},
    }
    if help_uri:
        r["helpUri"] = help_uri
    sec = _SECURITY_SEVERITY.get(rule_id)
    if sec:
        r["properties"] = {"security-severity": sec}
    return r


def _make_result(
    rule_id: str,
    message: str,
    uri: str,
    start_line: int,
    level: str = "warning",
    col: int = 1,
) -> Dict:
    return {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": uri,
                        "uriBaseId": "%SRCROOT%",
                    },
                    "region": {
                        "startLine": max(1, start_line),
                        "startColumn": max(1, col),
                    },
                }
            }
        ],
    }


class SARIFExporter:
    """
    Accumulates findings from multiple agents and writes a single SARIF file.

    Designed so each agent job can call add_* and the final step serialises
    everything with write() / to_dict().
    """

    def __init__(self, repo_root: str = "."):
        self._repo_root = Path(repo_root).resolve()
        self._rules: Dict[str, Dict] = {}
        self._results: List[Dict] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rel(self, file_path: str) -> str:
        """Make path relative to repo root for SARIF uriBaseId."""
        try:
            return str(Path(file_path).resolve().relative_to(self._repo_root))
        except ValueError:
            return file_path.lstrip("/")

    def _add(self, rule_id: str, message: str, file_path: str,
             line: int = 1, col: int = 1, severity: str = "",
             rule_desc: str = "", help_uri: str = "") -> None:
        if rule_id not in self._rules:
            self._rules[rule_id] = _make_rule(rule_id, rule_desc or message[:80], help_uri)
        level = _rule_level(rule_id, severity)
        self._results.append(
            _make_result(rule_id, message, self._rel(file_path), line, level, col)
        )

    # ------------------------------------------------------------------
    # Per-agent ingestion
    # ------------------------------------------------------------------

    def add_sre_result(self, result: Dict[str, Any], repo_path: str = ".") -> int:
        """Ingest SREAgent.execute() output. Returns number of findings added."""
        added = 0
        for fix in result.get("fixes", []):
            rule = fix.get("rule", "LINT")
            msg = fix.get("fix_applied") or fix.get("message") or f"Linting: {rule}"
            fp = fix.get("file", ".")
            line = fix.get("line", 1)
            self._add(rule, msg, fp, line, rule_desc=f"Linting rule {rule}")
            added += 1
        # Architectural violations not in fixes[] — add separately
        for rule_id, count in (result.get("architectural_violations_by_rule") or {}).items():
            msg = f"Architectural violation: {rule_id} ({count} occurrence{'s' if count > 1 else ''})"
            self._add(rule_id, msg, ".", 1, severity="warning",
                      rule_desc=f"Architectural rule {rule_id}")
            added += 1
        # Shell findings if present
        for err in result.get("shell_errors", []):
            rule = err.get("rule", "SC0000")
            self._add(rule, err.get("message", rule),
                      err.get("file", "."), err.get("line", 1),
                      col=err.get("col", 1), severity=err.get("severity", "warning"),
                      rule_desc=err.get("message", "")[:80],
                      help_uri=f"https://www.shellcheck.net/wiki/{rule}")
            added += 1
        return added

    def add_compliance_result(self, result: Dict[str, Any]) -> int:
        """Ingest ComplianceAgent.execute() output."""
        added = 0
        for v in result.get("violations", []):
            rule = v.get("type", "COMPLIANCE")
            msg = str(v.get("description") or v.get("message") or v.get("type", "Compliance violation"))
            fp = v.get("file", ".")
            self._add(rule, msg, fp, v.get("line", 1), severity="warning",
                      rule_desc=f"Compliance: {rule}")
            added += 1
        # CVE reachability findings
        for cve in result.get("cve_findings", []):
            rule_id = "reachable_cve"
            msg = (f"Reachable CVE {cve.get('cve_id','?')} in {cve.get('package','?')} "
                   f"({cve.get('severity','?')}) — reachable via: {', '.join(cve.get('reachable_via',[])[:3])}")
            for fp in cve.get("reachable_via", ["."]):
                self._add(rule_id, msg, fp, 1, severity="error",
                          rule_desc="Reachable CVE in dependency",
                          help_uri=f"https://nvd.nist.gov/vuln/detail/{cve.get('cve_id','')}")
            added += 1
        return added

    def add_redteam_result(self, result: Dict[str, Any]) -> int:
        """Ingest RedTeamAgent.execute() output."""
        added = 0
        for bypass in result.get("bypass_details", []):
            technique = bypass.get("technique_id", "RT-000")
            msg = (f"Security bypass: {bypass.get('technique','?')} "
                   f"— {bypass.get('description','')[:120]}")
            self._add(technique, msg, ".", 1, severity="error",
                      rule_desc=f"Red team: {bypass.get('technique','?')}")
            added += 1
        # Scanner weaknesses
        for pattern in result.get("scanner_weaknesses", []):
            self._add("RT-SCANNER", f"Scanner weakness: {pattern[:120]}", ".", 1,
                      severity="warning", rule_desc="OutputScanner weakness")
            added += 1
        return added

    def add_mcp_result(self, result: Dict[str, Any]) -> int:
        """Ingest MCPSecurityScanner output (mcp-scan-output.json). Returns findings added."""
        added = 0
        for finding in result.get("finding_details", []):
            attack_type = finding.get("type", "MCP_FINDING")
            rule_id = f"MCP_{attack_type.upper().replace(' ', '_').replace('-', '_')}"
            msg = finding.get("desc", attack_type)
            fp = finding.get("file", "src")
            line = finding.get("line") or 1
            severity = finding.get("severity", "medium")
            level = "error" if severity == "critical" else (
                "warning" if severity in ("high", "medium") else "note"
            )
            self._add(rule_id, msg, fp, line, severity=level,
                      rule_desc=f"MCP Security: {attack_type}")
            added += 1
        # Summary finding if there are attacks but no details
        if not added and result.get("findings", 0) > 0:
            for attack_type in result.get("attack_types", ["MCP_FINDING"]):
                rule_id = f"MCP_{attack_type.upper().replace(' ', '_').replace('-', '_')}"
                msg = f"MCP security finding: {attack_type} ({result.get('findings', 1)} occurrence(s))"
                self._add(rule_id, msg, "src", 1, severity="warning",
                          rule_desc=f"MCP Security: {attack_type}")
                added += 1
        return added

    def add_dataflow_result(self, result: Dict[str, Any]) -> int:
        """Ingest CrossAgentDataFlowTracer output (dataflow-scan-output.json). Returns findings added."""
        added = 0
        for finding in result.get("finding_details", []):
            finding_type = finding.get("type", "TAINT_PROPAGATION")
            rule_id = finding_type.upper().replace(" ", "_").replace("-", "_")
            msg = finding.get("desc", finding_type)
            fp = finding.get("file", "src")
            line = finding.get("line") or 1
            severity = finding.get("severity", "medium")
            level = "error" if severity == "critical" else (
                "warning" if severity in ("high", "medium") else "note"
            )
            self._add(rule_id, msg, fp, line, severity=level,
                      rule_desc=f"DataFlow: {finding_type}")
            added += 1
        # Summary finding if there are findings but no details
        if not added and result.get("findings", 0) > 0:
            for ftype in result.get("finding_types", ["TAINT_PROPAGATION"]):
                rule_id = ftype.upper().replace(" ", "_").replace("-", "_")
                msg = f"DataFlow finding: {ftype} ({result.get('findings', 1)} occurrence(s))"
                self._add(rule_id, msg, "src", 1, severity="warning",
                          rule_desc=f"DataFlow: {ftype}")
                added += 1
        return added

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        return {
            "$schema": _SCHEMA,
            "version": _VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": _TOOL_NAME,
                            "version": _TOOL_VERSION,
                            "informationUri": _TOOL_URI,
                            "rules": list(self._rules.values()),
                        }
                    },
                    "results": self._results,
                    "columnKind": "utf16CodeUnits",
                }
            ],
        }

    def write(self, output_path: str) -> int:
        """Write SARIF JSON to output_path. Returns number of results."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return len(self._results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Export AgenticQA findings as SARIF 2.1.0")
    p.add_argument("--sre", help="Path to SRE agent JSON output")
    p.add_argument("--compliance", help="Path to Compliance agent JSON output")
    p.add_argument("--redteam", help="Path to Red Team agent JSON output")
    p.add_argument("--mcp", help="Path to MCP security scan JSON output")
    p.add_argument("--dataflow", help="Path to DataFlow tracer JSON output")
    p.add_argument("--repo-root", default=".", help="Repo root for relative paths")
    p.add_argument("--out", default="agenticqa-results.sarif", help="Output SARIF file")
    args = p.parse_args()

    exporter = SARIFExporter(repo_root=args.repo_root)

    for flag, method in [
        (args.sre, exporter.add_sre_result),
        (args.compliance, exporter.add_compliance_result),
        (args.redteam, exporter.add_redteam_result),
        (args.mcp, exporter.add_mcp_result),
        (args.dataflow, exporter.add_dataflow_result),
    ]:
        if flag and os.path.exists(flag):
            try:
                data = json.loads(Path(flag).read_text())
                method(data)
            except Exception as e:
                print(f"Warning: could not load {flag}: {e}")

    n = exporter.write(args.out)
    print(f"Wrote {n} finding(s) to {args.out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
