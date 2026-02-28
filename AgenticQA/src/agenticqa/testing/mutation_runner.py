"""
Mutation Testing Integration — wraps mutmut to report test kill rates.

When mutmut is not installed, returns a safe UNTESTED mock result.
All subprocess calls use timeouts and error handling to be CI-safe.
"""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Verdict thresholds
# ---------------------------------------------------------------------------
_VERDICT_THRESHOLDS = [
    (0.80, "STRONG"),
    (0.60, "ADEQUATE"),
    (0.30, "WEAK"),
    (0.0,  "UNTESTED"),
]


def _verdict_from_rate(kill_rate: float) -> str:
    for threshold, verdict in _VERDICT_THRESHOLDS:
        if kill_rate >= threshold:
            return verdict
    return "UNTESTED"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class MutationResult:
    total_mutants: int
    killed: int
    survived: int
    timeout: int
    kill_rate: float          # 0.0-1.0
    verdict: str              # STRONG | ADEQUATE | WEAK | UNTESTED
    survived_samples: List[str]  # first 5 survived mutant descriptions
    files_mutated: List[str]
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            "total_mutants": self.total_mutants,
            "killed": self.killed,
            "survived": self.survived,
            "timeout": self.timeout,
            "kill_rate": self.kill_rate,
            "verdict": self.verdict,
            "survived_samples": self.survived_samples,
            "files_mutated": self.files_mutated,
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class MutationRunner:
    """Run mutation testing via mutmut and parse results."""

    def run(
        self,
        repo_path: str,
        target_files: Optional[List[str]] = None,
        timeout_seconds: int = 300,
    ) -> MutationResult:
        if not self._is_mutmut_available():
            return self._mock_result("mutmut not installed")

        start = time.monotonic()
        try:
            cmd = ["mutmut", "run"]
            if target_files:
                paths = " ".join(target_files)
                cmd += [f"--paths-to-mutate={paths}"]
            subprocess.run(
                cmd,
                cwd=repo_path,
                timeout=timeout_seconds,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return self._mock_result("mutmut run timed out")
        except Exception as e:  # noqa: BLE001
            return self._mock_result(f"mutmut run failed: {e}")

        # Collect results output
        try:
            res = subprocess.run(
                ["mutmut", "results"],
                cwd=repo_path,
                timeout=30,
                capture_output=True,
                text=True,
            )
            output = res.stdout or ""
        except Exception:  # noqa: BLE001
            output = ""

        duration = time.monotonic() - start
        parsed = self._parse_mutmut_results(output)
        killed = parsed.get("killed", 0)
        survived = parsed.get("survived", 0)
        timeout_count = parsed.get("timeout", 0)
        samples = parsed.get("survived_samples", [])
        total = killed + survived + timeout_count
        kill_rate = killed / total if total > 0 else 0.0

        return MutationResult(
            total_mutants=total,
            killed=killed,
            survived=survived,
            timeout=timeout_count,
            kill_rate=round(kill_rate, 4),
            verdict=_verdict_from_rate(kill_rate),
            survived_samples=samples[:5],
            files_mutated=list(target_files) if target_files else [],
            duration_seconds=round(duration, 2),
        )

    def _is_mutmut_available(self) -> bool:
        try:
            r = subprocess.run(
                ["mutmut", "--version"],
                capture_output=True,
                timeout=10,
            )
            return r.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def _parse_mutmut_results(self, output: str) -> dict:
        """Parse mutmut results output into counts and samples.

        Expected lines:
            Killed (42):
            Survived (5):
            Timeout (3):
            1. path/file.py:10
        """
        result: dict = {
            "killed": 0,
            "survived": 0,
            "timeout": 0,
            "survived_samples": [],
        }

        current_section: Optional[str] = None
        survived_samples: List[str] = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            killed_m = re.match(r"Killed\s*\((\d+)\)", line, re.IGNORECASE)
            survived_m = re.match(r"Survived\s*\((\d+)\)", line, re.IGNORECASE)
            timeout_m = re.match(r"Timeout\s*\((\d+)\)", line, re.IGNORECASE)

            if killed_m:
                result["killed"] = int(killed_m.group(1))
                current_section = "killed"
            elif survived_m:
                result["survived"] = int(survived_m.group(1))
                current_section = "survived"
            elif timeout_m:
                result["timeout"] = int(timeout_m.group(1))
                current_section = "timeout"
            elif current_section == "survived" and re.match(r"\d+\.", line):
                survived_samples.append(line)

        result["survived_samples"] = survived_samples[:5]
        return result

    def _mock_result(self, reason: str) -> MutationResult:
        return MutationResult(
            total_mutants=0,
            killed=0,
            survived=0,
            timeout=0,
            kill_rate=0.0,
            verdict="UNTESTED",
            survived_samples=[],
            files_mutated=[],
            duration_seconds=0.0,
        )
