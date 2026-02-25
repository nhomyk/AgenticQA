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
    p.add_argument("--repo-root", default=".", help="Repo root for relative paths")
    p.add_argument("--out", default="agenticqa-results.sarif", help="Output SARIF file")
    args = p.parse_args()

    exporter = SARIFExporter(repo_root=args.repo_root)
    total = 0

    for flag, method in [
        (args.sre, exporter.add_sre_result),
        (args.compliance, exporter.add_compliance_result),
        (args.redteam, exporter.add_redteam_result),
    ]:
        if flag and os.path.exists(flag):
            try:
                data = json.loads(Path(flag).read_text())
                total += method(data)
            except Exception as e:
                print(f"Warning: could not load {flag}: {e}")

    n = exporter.write(args.out)
    print(f"Wrote {n} finding(s) to {args.out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
