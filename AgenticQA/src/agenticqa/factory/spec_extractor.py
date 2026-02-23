"""
Natural language → AgentSpec extractor.

Converts a free-form client description into a structured AgentSpec that
AgentFactory.scaffold() can consume directly.  Uses Claude (Haiku by default)
for extraction with a keyword-based fallback when the LLM is unavailable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


VALID_FRAMEWORKS = frozenset({
    "langgraph", "langchain", "crewai", "autogen", "custom", "sandboxed"
})

_SYSTEM_PROMPT = """\
You are a JSON extraction assistant for AgenticQA, a multi-agent CI/CD governance platform.

Given a plain-English description of an agent, output ONLY a valid JSON object with exactly \
these fields — no markdown, no explanation, no extra keys:

{
  "agent_name": "<snake_case identifier, max 40 chars, letters/digits/underscores only>",
  "description": "<one sentence summary of the agent's purpose>",
  "capabilities": ["<2 to 6 short action strings, e.g. scan_code, report_findings>"],
  "framework": "<exactly one of: langgraph, langchain, crewai, autogen, custom, sandboxed>",
  "scope": {
    "file_patterns": ["<glob patterns the agent should read, e.g. **/*.py>"],
    "languages": ["<programming languages involved, e.g. python>"]
  },
  "checks": ["<2 to 5 short quality gate strings, e.g. no_secrets, valid_json_output>"]
}

Rules:
- agent_name must be snake_case, lowercase, contain only [a-z0-9_], max 40 characters
- capabilities must have between 2 and 6 items
- framework must be exactly one of the 6 values listed; default to sandboxed when unsure
- checks must have between 2 and 5 items
- Output ONLY the JSON object. No markdown fences. No commentary. No extra keys.\
"""

_CAPABILITY_KEYWORDS: Dict[str, str] = {
    "scan": "scan_code",
    "lint": "lint_files",
    "test": "run_tests",
    "secur": "security_check",
    "docker": "build_container",
    "deploy": "deploy_artifact",
    "review": "review_code",
    "report": "report_findings",
    "search": "search_files",
    "monitor": "monitor_metrics",
    "access": "accessibility_check",
    "coverage": "check_coverage",
    "format": "format_code",
    "audit": "audit_logs",
    "valid": "validate_output",
}

_FRAMEWORK_KEYWORDS: Dict[str, str] = {
    "langgraph": "langgraph",
    "langchain": "langchain",
    "crewai": "crewai",
    "autogen": "autogen",
    "custom": "custom",
}

_STOP_WORDS = frozenset({
    "a", "an", "the", "that", "which", "and", "or", "for", "to", "in",
    "of", "with", "is", "are", "it", "its", "my", "our", "your",
    "all", "any", "each", "from", "on", "at", "by", "as", "be",
})


@dataclass
class AgentSpec:
    """Structured representation of a client-defined agent."""

    agent_name: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    framework: str = "sandboxed"
    scope: Dict[str, Any] = field(default_factory=dict)
    checks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a dict compatible with AgentFactory.scaffold() kwargs."""
        return {
            "agent_name": self.agent_name,
            "capabilities": self.capabilities,
            "framework": self.framework,
            "scope": self.scope,
            "checks": self.checks,
        }


class NaturalLanguageSpecExtractor:
    """Converts a free-form description into an AgentSpec."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self._model = model

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def extract(self, description: str) -> AgentSpec:
        """Extract an AgentSpec from a natural language description.

        Tries the LLM first; falls back to keyword extraction if the LLM
        is unavailable or returns an invalid response.
        """
        if not description or not description.strip():
            return self._fallback_extract("generic_agent")

        llm_result = self._call_llm(description.strip())
        if llm_result:
            return AgentSpec(
                agent_name=llm_result["agent_name"],
                description=llm_result["description"],
                capabilities=llm_result["capabilities"],
                framework=llm_result["framework"],
                scope=llm_result["scope"],
                checks=llm_result["checks"],
            )
        return self._fallback_extract(description)

    # ──────────────────────────────────────────────────────────────────────
    # LLM path
    # ──────────────────────────────────────────────────────────────────────

    def _call_llm(self, description: str) -> Optional[Dict[str, Any]]:
        """Call the LLM and return the parsed spec dict, or None on any failure."""
        try:
            import anthropic  # type: ignore  # optional dependency

            client = anthropic.Anthropic()
            message = client.messages.create(
                model=self._model,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": description}],
            )
            raw_text = message.content[0].text.strip()
            # Strip any accidental markdown fences
            raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text).strip()
            return self._parse_llm_response(raw_text)
        except Exception:
            return None

    def _parse_llm_response(self, raw_text: str) -> Optional[Dict[str, Any]]:
        try:
            d = json.loads(raw_text)
            if self._validate_spec_dict(d):
                return d
            return None
        except (json.JSONDecodeError, ValueError):
            return None

    def _validate_spec_dict(self, d: Dict[str, Any]) -> bool:
        """Return True only if d has all required fields with valid values."""
        required = {"agent_name", "description", "capabilities", "framework", "scope", "checks"}
        if not required.issubset(d.keys()):
            return False
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", str(d.get("agent_name", ""))):
            return False
        caps = d.get("capabilities", [])
        if not isinstance(caps, list) or not (2 <= len(caps) <= 6):
            return False
        if d.get("framework") not in VALID_FRAMEWORKS:
            return False
        checks = d.get("checks", [])
        if not isinstance(checks, list) or not (2 <= len(checks) <= 5):
            return False
        if not isinstance(d.get("scope"), dict):
            return False
        return True

    # ──────────────────────────────────────────────────────────────────────
    # Fallback path (no network)
    # ──────────────────────────────────────────────────────────────────────

    def _fallback_extract(self, description: str) -> AgentSpec:
        """Keyword-based extraction — always returns a valid AgentSpec."""
        lower = description.lower()

        # agent_name: first 4 significant words joined as snake_case
        words = re.findall(r"[a-z]+", lower)
        sig = [w for w in words if w not in _STOP_WORDS][:4]
        name = "_".join(sig)[:40] if sig else "custom_agent"
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name):
            name = "custom_agent"

        # capabilities: keyword matching
        caps: List[str] = []
        for kw, cap in _CAPABILITY_KEYWORDS.items():
            if kw in lower and cap not in caps:
                caps.append(cap)
        if len(caps) < 2:
            caps = ["run_task", "report_results"]
        caps = caps[:6]

        # framework: first keyword match, else sandboxed
        framework = "sandboxed"
        for kw, fw in _FRAMEWORK_KEYWORDS.items():
            if kw in lower:
                framework = fw
                break

        # file patterns based on language hints
        if "typescript" in lower or " tsx" in lower or ".tsx" in lower:
            file_patterns = ["**/*.ts", "**/*.tsx"]
            languages = ["typescript"]
        elif "javascript" in lower or " jsx" in lower or ".jsx" in lower or " js " in lower:
            file_patterns = ["**/*.js", "**/*.jsx"]
            languages = ["javascript"]
        elif "go " in lower or "golang" in lower:
            file_patterns = ["**/*.go"]
            languages = ["go"]
        elif "ruby" in lower or ".rb" in lower:
            file_patterns = ["**/*.rb"]
            languages = ["ruby"]
        else:
            file_patterns = ["**/*.py"]
            languages = ["python"]

        checks = ["no_secrets", "valid_json_output"]

        return AgentSpec(
            agent_name=name,
            description=description[:200],
            capabilities=caps,
            framework=framework,
            scope={"file_patterns": file_patterns, "languages": languages},
            checks=checks,
        )
