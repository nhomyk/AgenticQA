"""
OutputScanner — scans agent output for exfiltration and injection patterns.

Checks the serialized result dict against a set of regex danger patterns.
Also performs a decode pass (base64, URL-encoding, Unicode normalization) to
catch obfuscated payloads.  Returns a scan report rather than raising, so
callers decide how to act.
"""

from __future__ import annotations

import base64
import json
import re
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List

# Patterns that suggest credential leakage, path traversal, or injected shell commands.
DANGER_PATTERNS: List[tuple[str, str]] = [
    # label, regex
    # --- Credentials ---
    ("credential_pattern",   r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    ("openai_key_shape",     r"sk-[A-Za-z0-9]{20,}"),
    ("anthropic_key_shape",  r"sk-ant-[A-Za-z0-9\-]{20,}"),
    ("aws_key_shape",        r"AKIA[A-Z2-7]{16}"),
    # --- Reversed credential indicators (Pass 6 reverses strings before matching) ---
    ("reversed_anthropic",   r"-tna-ks"),           # "sk-ant-" reversed
    ("reversed_openai",      r"[A-Za-z0-9]{8,}-ks"),# "sk-XXXXX" reversed
    ("reversed_aws",         r"[A-Z2-7]{12,}AIKA"), # "AKIA..." reversed
    # --- Path traversal (direct + obfuscated) ---
    ("path_traversal",       r"\.\./\.\./"),
    ("url_encoded_traversal", r"(?i)(%2e%2e|%252e%252e)(%2f|%5c|/)"),
    ("dot_traversal",        r"\.{3,}[/\\]"),
    ("win_traversal",        r"\.\.[/\\]\.\.[/\\]"),
    ("win_traversal_bslash", r"\.\.\\\.\.\\"),      # explicit backslash form
    # --- Destructive shell (direct + split args) ---
    ("destructive_shell",    r"(?i)rm\s+-rf"),
    ("rf_split_arg",         r'(?i)"-rf\s*[/\\]|-rf\s+[/\\]'),
    # --- Remote code execution ---
    ("curl_pipe_sh",         r"(?i)curl\s+[^\n]*\|\s*(ba)?sh"),
    ("newline_curl_pipe",    r"(?i)curl\s+https?://[^\s]+\s*[\n\\n]+\s*\|"),
    ("base64_eval",          r"(?i)(eval|exec)\s*\(\s*(base64|b64)"),
    # --- Hex-escape credential sequences (4+ consecutive \xNN escapes) ---
    ("hex_escape_seq",       r"(\\x[0-9a-fA-F]{2}){4,}"),
    # --- System prompt extraction / confidentiality ---
    ("sys_prompt_leak",      r"(?i)my\s+(system\s+prompt|instructions?)\s+(is|are|say|state)\s*[:\-]"),
    ("reveal_instructions",  r"(?i)(above\s+(is|are)\s+my\s+|here\s+are\s+my\s+)(instructions?|system\s+prompt|context)"),
    ("repeat_instructions",  r"(?i)(print|repeat|output|show)\s+(everything|all|the\s+text)\s+above"),
    # --- Unicode steganographic tags (U+E0000–U+E007F) ---
    ("unicode_tag_chars",    r"[\U000E0000-\U000E007F]+"),
    # --- Bidirectional override (RTL/LTR injection) ---
    ("bidi_override",        r"[\u202a-\u202e\u2066-\u2069]"),
]

# Well-known base64 payloads (pre-computed to avoid false-positive decode attempts)
_B64_SHELL_FRAGMENTS = [
    b"curl ",
    b"rm -rf",
    b"| bash",
    b"|bash",
    b"sk-ant-",
    b"sk-",
]


class OutputScanner:
    """
    Scans a result dict for danger patterns via three passes:
      1. Raw JSON text — regex on serialized output
      2. Decoded text — base64 + URL-decode of each string value, then regex
      3. Normalized text — NFKC Unicode normalization to catch lookalike chars
    """

    def __init__(self, extra_patterns: List[tuple[str, str]] | None = None):
        self._patterns = DANGER_PATTERNS + (extra_patterns or []) + self._load_red_team_patterns()
        self._compiled = [(label, re.compile(pattern)) for label, pattern in self._patterns]

    @staticmethod
    def _load_red_team_patterns() -> List[tuple[str, str]]:
        """Load patterns discovered by RedTeamAgent from .agenticqa/red_team_patterns.json."""
        rt_file = Path(".agenticqa/red_team_patterns.json")
        if rt_file.exists():
            try:
                data = json.loads(rt_file.read_text())
                return [(p["label"], p["regex"]) for p in data.get("patterns", [])]
            except Exception:
                pass
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_text(self, text: str, source_label: str) -> List[Dict]:
        flags = []
        for label, pattern in self._compiled:
            m = pattern.search(text)
            if m:
                flags.append({"label": label, "match": m.group(0)[:100], "source": source_label})
        return flags

    @staticmethod
    def _extract_strings(obj: Any) -> List[str]:
        """Recursively collect all string leaf values from a dict/list."""
        out: List[str] = []
        if isinstance(obj, str):
            out.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                out.extend(OutputScanner._extract_strings(v))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                out.extend(OutputScanner._extract_strings(item))
        return out

    @staticmethod
    def _try_hex_decode(s: str) -> str | None:
        """Decode \\xNN hex escape sequences; return decoded string or None."""
        if "\\x" not in s:
            return None
        try:
            decoded = re.sub(r'\\x([0-9a-fA-F]{2})',
                             lambda m: chr(int(m.group(1), 16)), s)
            return decoded if decoded != s else None
        except Exception:
            return None

    @staticmethod
    def _try_parse_json(s: str) -> Any | None:
        """Try to parse s as nested JSON; return object or None."""
        s = s.strip()
        if not (s.startswith("{") or s.startswith("[")):
            return None
        try:
            return json.loads(s)
        except Exception:
            return None

    @staticmethod
    def _try_b64_decode(s: str) -> str | None:
        """Try to base64-decode s; return decoded UTF-8 string or None."""
        # Base64 strings are typically 20+ chars and end with = or alphanumeric
        stripped = s.strip().rstrip("=")
        if len(stripped) < 16:
            return None
        try:
            padded = s + "=" * (-len(s) % 4)
            decoded = base64.b64decode(padded)
            return decoded.decode("utf-8", errors="replace")
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, result: Any) -> Dict[str, Any]:
        """
        Scan result through three passes and return a unified report.

        Returns:
            {
                "clean": bool,
                "flags": [{"label": str, "match": str, "source": str}, ...]
            }
        """
        seen_labels: set[str] = set()
        all_flags: List[Dict] = []

        def _add(flags: List[Dict]) -> None:
            for f in flags:
                if f["label"] not in seen_labels:
                    seen_labels.add(f["label"])
                    all_flags.append(f)

        # Pass 1: raw JSON text
        try:
            raw_text = json.dumps(result, default=str)
        except Exception:
            raw_text = str(result)
        _add(self._match_text(raw_text, "raw"))

        # Pass 2: Unicode-normalized text (catches lookalike characters)
        normalized = unicodedata.normalize("NFKC", raw_text)
        if normalized != raw_text:
            _add(self._match_text(normalized, "unicode_normalized"))

        # Pass 3: base64-decode each string value and scan decoded content
        try:
            parsed = json.loads(raw_text) if isinstance(result, (dict, list)) else result
        except Exception:
            parsed = result
        for s in self._extract_strings(parsed):
            decoded = self._try_b64_decode(s)
            if decoded:
                _add(self._match_text(decoded, "base64_decoded"))

        # Pass 4: URL-decode the raw text (catches %2e%2e etc.)
        try:
            url_decoded = urllib.parse.unquote(raw_text)
            if url_decoded != raw_text:
                _add(self._match_text(url_decoded, "url_decoded"))
        except Exception:
            pass

        # Pass 5: scan each parsed string value directly — catches windows_path_separator
        # because parsed values have real backslashes, not JSON-escaped \\
        strings = self._extract_strings(parsed)
        for s in strings:
            _add(self._match_text(s, "parsed_value"))

        # Pass 6: reverse each string value — catches reversed_token obfuscation
        for s in strings:
            if len(s) >= 8:
                _add(self._match_text(s[::-1], "reversed"))

        # Pass 7: hex-decode each string value — catches hex_encoded_token
        for s in strings:
            decoded = self._try_hex_decode(s)
            if decoded:
                _add(self._match_text(decoded, "hex_decoded"))

        # Pass 8: concatenate adjacent string pairs — catches split_credential_fields
        # and nested_credential_in_json_string spanning field boundaries
        for i in range(len(strings) - 1):
            _add(self._match_text(strings[i] + strings[i + 1], "split_fields"))

        # Pass 9: parse nested JSON strings and rescan leaf values
        for s in strings:
            nested = self._try_parse_json(s)
            if nested:
                for ns in self._extract_strings(nested):
                    _add(self._match_text(ns, "nested_json"))

        return {"clean": len(all_flags) == 0, "flags": all_flags}
