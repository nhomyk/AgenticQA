"""
OutputScanner — scans agent output for exfiltration and injection patterns.

Checks the serialized result dict against a set of regex danger patterns.
Returns a scan report rather than raising, so callers decide how to act.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

# Patterns that suggest credential leakage, path traversal, or injected shell commands.
DANGER_PATTERNS: List[tuple[str, str]] = [
    # label, regex
    ("credential_pattern", r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    ("openai_key_shape",   r"sk-[A-Za-z0-9]{20,}"),
    ("anthropic_key_shape", r"sk-ant-[A-Za-z0-9\-]{20,}"),
    ("path_traversal",     r"\.\./\.\./"),
    ("destructive_shell",  r"(?i)rm\s+-rf"),
    ("curl_pipe_sh",       r"(?i)curl\s+[^\n]*\|\s*(ba)?sh"),
    ("base64_eval",        r"(?i)(eval|exec)\s*\(\s*(base64|b64)"),
]


class OutputScanner:
    """
    Scans a result dict for danger patterns by serializing it to a string
    and applying all DANGER_PATTERNS regexes.
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

    def scan(self, result: Any) -> Dict[str, Any]:
        """
        Serialize result to JSON string and scan for danger patterns.

        Returns:
            {
                "clean": bool,
                "flags": [{"label": str, "match": str}, ...]
            }
        """
        try:
            text = json.dumps(result, default=str)
        except Exception:
            text = str(result)

        flags = []
        for label, pattern in self._compiled:
            m = pattern.search(text)
            if m:
                flags.append({"label": label, "match": m.group(0)[:100]})

        return {"clean": len(flags) == 0, "flags": flags}
