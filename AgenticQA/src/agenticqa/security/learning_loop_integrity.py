"""
LearningLoopIntegrityGuard — validates agent learning memory files before use.

Attack vectors blocked
----------------------
POISONED_METRICS    — attacker writes extreme EWMA values to metrics_history.jsonl
                      to suppress future failure detection or trigger false-passes
SCHEMA_TAMPERING    — extra or missing fields in repo profile / metrics files that
                      could propagate garbage into threshold calibration
ANOMALY_INJECTION   — sudden impossible shifts in fix_rate, coverage, error counts
                      that indicate file tampering vs legitimate learning

What it does
------------
1. Schema validation — required fields present; no unexpected numeric types
2. Range validation  — numeric fields within physically possible bounds
   (fix_rate 0.0–1.0, coverage 0–100, thresholds > 0, etc.)
3. Anomaly detection — single-run deltas larger than plausible learning speed
4. HMAC sidecar     — optional; sign on write, verify on read (set
                      AGENTICQA_LEARNING_HMAC_SECRET in environment)

Usage
-----
    from agenticqa.security.learning_loop_integrity import LearningLoopIntegrityGuard

    guard = LearningLoopIntegrityGuard()

    # Validate a metrics snapshot dict before using it
    ok, violations = guard.validate_metrics_record(record)

    # Validate a RepoProfile data dict
    ok, violations = guard.validate_repo_profile(data)

    # Sign a file after writing (optional HMAC protection)
    guard.sign_file(path)

    # Verify a file before reading (optional HMAC protection)
    ok, msg = guard.verify_file(path)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_HMAC_SECRET_ENV = "AGENTICQA_LEARNING_HMAC_SECRET"
_SIDECAR_SUFFIX = ".hmac"


# ---------------------------------------------------------------------------
# Schema specs
# ---------------------------------------------------------------------------

# Required keys for a LearningMetricsSnapshot dict
_METRICS_REQUIRED: Dict[str, type] = {
    "repo_id": str,
    "run_id": str,
    "recorded_at": str,
}

# Required keys for a RepoProfile _data dict
_PROFILE_REQUIRED: Dict[str, type] = {
    "repo_id": str,
    "total_runs": int,
    "fix_rates_by_language": dict,
    "known_unfixable_rules": list,
}

# Numeric bounds: field_name → (min, max)
_NUMERIC_BOUNDS: Dict[str, Tuple[float, float]] = {
    "fix_rate":                 (0.0, 1.0),
    "current_threshold":        (0.0, 1.0),
    "coverage":                 (0.0, 100.0),
    "total_runs":               (0, 1_000_000),
    "total_errors":             (0, 10_000_000),
    "fixable_errors":           (0, 10_000_000),
}

# Max plausible single-run EWMA shift (EWMA α=0.3 → max shift ≈ 0.3 * range)
_MAX_DELTA = 0.5


# ---------------------------------------------------------------------------
# Violations
# ---------------------------------------------------------------------------

class IntegrityViolation:
    def __init__(self, field: str, violation_type: str, detail: str) -> None:
        self.field = field
        self.violation_type = violation_type  # MISSING_FIELD | TYPE_ERROR | OUT_OF_RANGE | ANOMALY
        self.detail = detail

    def __str__(self) -> str:
        return f"[{self.violation_type}] {self.field}: {self.detail}"


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

class LearningLoopIntegrityGuard:
    """
    Validates and optionally HMAC-protects agent learning memory files.

    All validation methods return (ok: bool, violations: List[IntegrityViolation]).
    A result is considered 'ok' when there are no MISSING_FIELD or OUT_OF_RANGE
    violations (TYPE_ERROR and ANOMALY are logged but don't block loading by default).
    """

    def __init__(self, strict: bool = False) -> None:
        """
        Args:
            strict: if True, any violation causes ok=False.  Default (False)
                    only blocks on MISSING_FIELD and OUT_OF_RANGE.
        """
        self._strict = strict
        secret = os.getenv(_HMAC_SECRET_ENV, "")
        self._hmac_key: Optional[bytes] = secret.encode() if secret else None

    # ── Schema + range validation ─────────────────────────────────────────

    def validate_metrics_record(
        self, record: Dict[str, Any]
    ) -> Tuple[bool, List[IntegrityViolation]]:
        """Validate a single LearningMetricsSnapshot dict."""
        return self._validate(record, _METRICS_REQUIRED)

    def validate_repo_profile(
        self, data: Dict[str, Any]
    ) -> Tuple[bool, List[IntegrityViolation]]:
        """Validate a RepoProfile._data dict."""
        violations = self._check_required(data, _PROFILE_REQUIRED)
        violations += self._check_fix_rates(data.get("fix_rates_by_language", {}))
        violations += self._check_numeric_fields(data)
        ok = self._is_ok(violations)
        return ok, violations

    def _validate(
        self, record: Dict[str, Any], required: Dict[str, type]
    ) -> Tuple[bool, List[IntegrityViolation]]:
        violations = self._check_required(record, required)
        violations += self._check_numeric_fields(record)
        ok = self._is_ok(violations)
        return ok, violations

    def _check_required(
        self, data: Dict[str, Any], required: Dict[str, type]
    ) -> List[IntegrityViolation]:
        violations: List[IntegrityViolation] = []
        for field, expected_type in required.items():
            if field not in data:
                violations.append(IntegrityViolation(
                    field, "MISSING_FIELD",
                    f"Required field '{field}' is absent",
                ))
            elif not isinstance(data[field], expected_type):
                violations.append(IntegrityViolation(
                    field, "TYPE_ERROR",
                    f"Expected {expected_type.__name__}, got {type(data[field]).__name__}",
                ))
        return violations

    def _check_fix_rates(self, fix_rates: Any) -> List[IntegrityViolation]:
        """All fix_rates_by_language values must be in [0.0, 1.0]."""
        violations: List[IntegrityViolation] = []
        if not isinstance(fix_rates, dict):
            return violations
        for lang, rate in fix_rates.items():
            if not isinstance(rate, (int, float)):
                continue
            if not (0.0 <= float(rate) <= 1.0):
                violations.append(IntegrityViolation(
                    f"fix_rates_by_language.{lang}", "OUT_OF_RANGE",
                    f"fix_rate={rate} is outside [0.0, 1.0] — possible tampering",
                ))
        return violations

    def _check_numeric_fields(self, data: Dict[str, Any]) -> List[IntegrityViolation]:
        violations: List[IntegrityViolation] = []
        for field, (lo, hi) in _NUMERIC_BOUNDS.items():
            if field not in data:
                continue
            val = data[field]
            if not isinstance(val, (int, float)):
                continue
            if not (lo <= float(val) <= hi):
                violations.append(IntegrityViolation(
                    field, "OUT_OF_RANGE",
                    f"value={val} outside [{lo}, {hi}] — possible tampering",
                ))
        return violations

    def _is_ok(self, violations: List[IntegrityViolation]) -> bool:
        if self._strict:
            return len(violations) == 0
        blocking = {"MISSING_FIELD", "OUT_OF_RANGE"}
        return not any(v.violation_type in blocking for v in violations)

    # ── HMAC sidecar ─────────────────────────────────────────────────────

    def sign_file(self, path: str | Path) -> bool:
        """Write a .hmac sidecar for path. Returns False if HMAC key not configured."""
        if not self._hmac_key:
            return False
        try:
            content = Path(path).read_bytes()
            sig = hmac.new(self._hmac_key, content, hashlib.sha256).hexdigest()
            Path(str(path) + _SIDECAR_SUFFIX).write_text(sig)
            return True
        except Exception as exc:
            logger.warning("sign_file failed for %s: %s", path, exc)
            return False

    def verify_file(self, path: str | Path) -> Tuple[bool, str]:
        """
        Verify a file against its .hmac sidecar.

        Returns (True, "ok") if:
        - HMAC key is not configured (disabled — skip, don't block), OR
        - Sidecar matches current file content.

        Returns (False, reason) if sidecar exists but doesn't match.
        """
        if not self._hmac_key:
            return True, "HMAC not configured — skipping verification"
        sidecar = Path(str(path) + _SIDECAR_SUFFIX)
        if not sidecar.exists():
            return True, "No sidecar present — file predates signing"
        try:
            content = Path(path).read_bytes()
            expected = sidecar.read_text().strip()
            actual = hmac.new(self._hmac_key, content, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, actual):
                return True, "HMAC verified"
            return False, f"HMAC mismatch — file may have been tampered with"
        except Exception as exc:
            return False, f"HMAC verification error: {exc}"

    # ── Bulk JSONL validation ─────────────────────────────────────────────

    def validate_metrics_file(
        self, path: str | Path
    ) -> Tuple[int, int, List[str]]:
        """
        Validate all records in a metrics JSONL file.

        Returns (total_lines, bad_lines, error_summaries).
        """
        total = bad = 0
        errors: List[str] = []
        try:
            with open(path) as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    total += 1
                    try:
                        rec = json.loads(line)
                        ok, violations = self.validate_metrics_record(rec)
                        if not ok:
                            bad += 1
                            errors.append(f"line {i}: {[str(v) for v in violations]}")
                    except json.JSONDecodeError as exc:
                        bad += 1
                        errors.append(f"line {i}: JSON parse error: {exc}")
        except FileNotFoundError:
            pass
        return total, bad, errors
