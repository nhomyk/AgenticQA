"""Shadow AI / unauthorized model detection.

Detects when code or agents use AI models that are not on the
organization's approved list.  Scans source files for:
  - Direct API calls (openai.ChatCompletion, anthropic.Anthropic, etc.)
  - Model IDs in strings ("gpt-4", "claude-3", etc.)
  - Imports of unapproved AI libraries
  - Environment variables pointing to AI services

Inspired by the finding that 78% of AI users bring their own tools
to work (McKinsey 2025) and 68% of CISOs admit using unauthorized
AI tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set


# ── Default approved models ──────────────────────────────────────────────────

DEFAULT_APPROVED_MODELS: FrozenSet[str] = frozenset({
    # Anthropic
    "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    # Can be extended per organization
})

DEFAULT_APPROVED_PROVIDERS: FrozenSet[str] = frozenset({
    "anthropic",
})

# Known model ID patterns (provider → regex list)
_MODEL_PATTERNS: List[tuple] = [
    ("openai", re.compile(r"""["'](?:gpt-4[o\-turbo]*|gpt-3\.5-turbo|o1(?:-mini|-preview)?|dall-e-\d|whisper-\d|text-embedding-(?:3-(?:small|large)|ada))["']""", re.I)),
    ("anthropic", re.compile(r"""["']claude-(?:opus|sonnet|haiku|3|instant)[-\w]*["']""", re.I)),
    ("google", re.compile(r"""["'](?:gemini-(?:pro|ultra|nano|flash|2\.0)[-\w]*|palm\d?)["']""", re.I)),
    ("meta", re.compile(r"""["'](?:llama[-\s]?\d|codellama)[-\w]*["']""", re.I)),
    ("mistral", re.compile(r"""["'](?:mistral[-\w]*|mixtral[-\w]*)["']""", re.I)),
    ("cohere", re.compile(r"""["'](?:command[-\w]*|embed[-\w]*)["']""", re.I)),
    ("deepseek", re.compile(r"""["']deepseek[-\w]*["']""", re.I)),
]

# AI library imports that indicate provider usage
_PROVIDER_IMPORTS: Dict[str, List[str]] = {
    "openai": ["import openai", "from openai"],
    "google": ["import google.generativeai", "from google.generativeai",
               "import vertexai", "from vertexai"],
    "cohere": ["import cohere", "from cohere"],
    "replicate": ["import replicate", "from replicate"],
    "huggingface": ["import transformers", "from transformers",
                    "from huggingface_hub"],
    "deepseek": ["import deepseek", "from deepseek"],
    "mistral": ["from mistralai", "import mistralai"],
}

# AI-related env var patterns
_AI_ENV_VARS = re.compile(
    r"""os\.(?:getenv|environ)\s*[\[(]\s*["']"""
    r"""(OPENAI_API_KEY|GOOGLE_API_KEY|COHERE_API_KEY|"""
    r"""REPLICATE_API_TOKEN|HF_TOKEN|HUGGING_FACE_HUB_TOKEN|"""
    r"""DEEPSEEK_API_KEY|MISTRAL_API_KEY|GROQ_API_KEY|"""
    r"""TOGETHER_API_KEY|FIREWORKS_API_KEY|ANYSCALE_API_KEY)"""
    r"""["']""",
    re.I,
)


@dataclass
class ShadowAIFinding:
    """A single unauthorized model/provider usage."""
    rule_id: str  # UNAPPROVED_MODEL, UNAPPROVED_PROVIDER, SHADOW_ENV_VAR
    provider: str
    model_id: str = ""
    file_path: str = ""
    line_number: int = 0
    evidence: str = ""
    severity: str = "high"


@dataclass
class ShadowAIReport:
    """Results of a shadow AI scan."""
    findings: List[ShadowAIFinding] = field(default_factory=list)
    files_scanned: int = 0
    approved_models: List[str] = field(default_factory=list)
    approved_providers: List[str] = field(default_factory=list)

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def has_shadow_ai(self) -> bool:
        return len(self.findings) > 0

    @property
    def providers_found(self) -> Set[str]:
        return {f.provider for f in self.findings}


class ShadowAIDetector:
    """Detects unauthorized AI model usage in source code.

    Usage::

        detector = ShadowAIDetector(
            approved_models={"claude-opus-4-6", "claude-sonnet-4-6"},
            approved_providers={"anthropic"},
        )
        report = detector.scan("/path/to/repo")
    """

    def __init__(
        self,
        approved_models: Optional[Set[str]] = None,
        approved_providers: Optional[Set[str]] = None,
    ) -> None:
        self.approved_models = approved_models or set(DEFAULT_APPROVED_MODELS)
        self.approved_providers = approved_providers or set(DEFAULT_APPROVED_PROVIDERS)

    def scan(self, repo_path: str) -> ShadowAIReport:
        """Scan a repository for unauthorized AI model usage."""
        report = ShadowAIReport(
            approved_models=sorted(self.approved_models),
            approved_providers=sorted(self.approved_providers),
        )

        root = Path(repo_path)
        if not root.is_dir():
            return report

        try:
            from agenticqa.security.safe_file_iter import iter_source_files, safe_read_text
        except ImportError:
            return report

        source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".kt", ".rs"}
        for fpath in iter_source_files(root, extensions=source_exts, max_files=10_000):
            content = safe_read_text(fpath)
            if not content:
                continue
            report.files_scanned += 1
            rel = str(fpath.relative_to(root))
            self._scan_file(content, rel, report)

        return report

    def scan_text(self, text: str, file_path: str = "<inline>") -> ShadowAIReport:
        """Scan a single text blob for unauthorized model usage."""
        report = ShadowAIReport(
            approved_models=sorted(self.approved_models),
            approved_providers=sorted(self.approved_providers),
        )
        report.files_scanned = 1
        self._scan_file(text, file_path, report)
        return report

    def _scan_file(self, content: str, file_path: str,
                   report: ShadowAIReport) -> None:
        lines = content.split("\n")

        # 1. Check for model IDs
        for provider, pattern in _MODEL_PATTERNS:
            for i, line in enumerate(lines, 1):
                for m in pattern.finditer(line):
                    model_id = m.group().strip("\"'")
                    if model_id not in self.approved_models:
                        report.findings.append(ShadowAIFinding(
                            rule_id="UNAPPROVED_MODEL",
                            provider=provider,
                            model_id=model_id,
                            file_path=file_path,
                            line_number=i,
                            evidence=line.strip()[:200],
                        ))

        # 2. Check for unapproved provider imports
        for provider, import_strs in _PROVIDER_IMPORTS.items():
            if provider in self.approved_providers:
                continue
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                for imp in import_strs:
                    if stripped.startswith(imp):
                        report.findings.append(ShadowAIFinding(
                            rule_id="UNAPPROVED_PROVIDER",
                            provider=provider,
                            file_path=file_path,
                            line_number=i,
                            evidence=stripped[:200],
                        ))
                        break

        # 3. Check for AI-related environment variables
        for i, line in enumerate(lines, 1):
            for m in _AI_ENV_VARS.finditer(line):
                env_var = m.group(1)
                # Determine provider from env var
                provider = "unknown"
                env_lower = env_var.lower()
                for p in ["openai", "google", "cohere", "replicate",
                          "deepseek", "mistral", "groq", "together",
                          "fireworks", "anyscale"]:
                    if p in env_lower:
                        provider = p
                        break
                if "hf_" in env_lower or "hugging" in env_lower:
                    provider = "huggingface"

                if provider not in self.approved_providers:
                    report.findings.append(ShadowAIFinding(
                        rule_id="SHADOW_ENV_VAR",
                        provider=provider,
                        file_path=file_path,
                        line_number=i,
                        evidence=f"env var: {env_var}",
                        severity="medium",
                    ))
