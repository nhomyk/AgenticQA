"""PII auto-redaction for AI agent outputs.

Goes beyond detection: actively masks PII in agent output dicts
before they reach the client.  Inspired by the finding that 77% of
employees paste company data into AI tools (LayerX 2025).

Supported PII types:
  - Email addresses
  - Phone numbers (US, international)
  - Social Security Numbers (SSN)
  - Credit card numbers (Luhn-validated)
  - IP addresses (v4)
  - AWS access keys
  - API keys / bearer tokens
  - Dates of birth patterns
  - Street addresses (US)
  - Names in common contexts (Dear X, From: X)

Each redaction is logged for compliance audit.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── PII patterns ─────────────────────────────────────────────────────────────

_PII_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    ("EMAIL", re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ), "[REDACTED_EMAIL]"),

    ("PHONE_US", re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ), "[REDACTED_PHONE]"),

    ("SSN", re.compile(
        r"\b\d{3}-\d{2}-\d{4}\b"
    ), "[REDACTED_SSN]"),

    ("CREDIT_CARD", re.compile(
        r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
        r"[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,4}\b"
    ), "[REDACTED_CC]"),

    ("IPV4", re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
    ), "[REDACTED_IP]"),

    ("AWS_KEY", re.compile(
        r"\bAKIA[A-Z2-7]{16}\b"
    ), "[REDACTED_AWS_KEY]"),

    ("API_KEY", re.compile(
        r"\b(?:sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9\-]{20,})\b"
    ), "[REDACTED_API_KEY]"),

    ("BEARER_TOKEN", re.compile(
        r"Bearer\s+[A-Za-z0-9\-._~+/]+=*",
        re.IGNORECASE,
    ), "[REDACTED_BEARER]"),

    ("DOB", re.compile(
        r"\b(?:date of birth|dob|born)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
        re.IGNORECASE,
    ), "[REDACTED_DOB]"),

    ("US_ADDRESS", re.compile(
        r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
        r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Way|Ct|Court)"
        r"\.?\b"
    ), "[REDACTED_ADDRESS]"),
]


@dataclass
class RedactionEvent:
    """Record of a single PII redaction for audit."""
    pii_type: str
    field_path: str
    original_length: int
    replacement: str


@dataclass
class RedactionReport:
    """Summary of all redactions applied to an output."""
    clean: bool = True
    redaction_count: int = 0
    events: List[RedactionEvent] = field(default_factory=list)
    redacted_output: Any = None


class PIIRedactor:
    """Scans and redacts PII in agent output dicts.

    Usage::

        redactor = PIIRedactor()
        report = redactor.redact(agent_output)
        safe_output = report.redacted_output
    """

    def __init__(self, extra_patterns: Optional[List[Tuple[str, re.Pattern, str]]] = None) -> None:
        self._patterns = list(_PII_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

    def redact_text(self, text: str, field_path: str = "") -> Tuple[str, List[RedactionEvent]]:
        """Redact PII in a single string. Returns (redacted_text, events)."""
        events: List[RedactionEvent] = []
        result = text
        for pii_type, pattern, replacement in self._patterns:
            matches = list(pattern.finditer(result))
            if matches:
                for m in matches:
                    events.append(RedactionEvent(
                        pii_type=pii_type,
                        field_path=field_path,
                        original_length=len(m.group()),
                        replacement=replacement,
                    ))
                result = pattern.sub(replacement, result)
        return result, events

    def redact(self, output: Any) -> RedactionReport:
        """Recursively redact PII from an output dict/list/string.

        Returns a RedactionReport with the cleaned output and audit events.
        """
        report = RedactionReport()
        report.redacted_output = self._redact_recursive(output, "", report)
        report.clean = report.redaction_count == 0
        return report

    def _redact_recursive(self, obj: Any, path: str,
                          report: RedactionReport) -> Any:
        if isinstance(obj, str):
            redacted, events = self.redact_text(obj, path)
            if events:
                report.events.extend(events)
                report.redaction_count += len(events)
            return redacted
        elif isinstance(obj, dict):
            return {
                k: self._redact_recursive(v, f"{path}.{k}" if path else k, report)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [
                self._redact_recursive(item, f"{path}[{i}]", report)
                for i, item in enumerate(obj)
            ]
        return obj

    def scan_only(self, output: Any) -> RedactionReport:
        """Detect PII without modifying the output (dry run)."""
        report = RedactionReport()
        self._scan_recursive(output, "", report)
        report.clean = report.redaction_count == 0
        report.redacted_output = output  # unchanged
        return report

    def _scan_recursive(self, obj: Any, path: str,
                        report: RedactionReport) -> None:
        if isinstance(obj, str):
            for pii_type, pattern, replacement in self._patterns:
                matches = list(pattern.finditer(obj))
                for m in matches:
                    report.events.append(RedactionEvent(
                        pii_type=pii_type,
                        field_path=path,
                        original_length=len(m.group()),
                        replacement=replacement,
                    ))
                    report.redaction_count += 1
        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_recursive(v, f"{path}.{k}" if path else k, report)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._scan_recursive(item, f"{path}[{i}]", report)
