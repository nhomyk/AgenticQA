"""
AI Model Supply Chain SBOM (Software Bill of Materials).

Scans a repository for all AI/ML model dependencies and produces a
structured inventory covering:
- Provider and model ID (HuggingFace, OpenAI, Anthropic, Google, PyTorch, etc.)
- License classification (permissive / restricted / proprietary / unknown)
- Risk flags: UNKNOWN_LICENSE, RESTRICTED_LICENSE, EXTERNAL_API,
              DEPRECATED_MODEL, UNVERSIONED_MODEL
- EU AI Act Art. 13 evidence artifact

Pure Python (re, ast, pathlib). No network calls. No external tools required.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__",
    ".git", "dist", "build", ".next", "out",
}

# ---------------------------------------------------------------------------
# Provider detection — triggered by import statements
# ---------------------------------------------------------------------------

_PROVIDER_IMPORT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(from|import)\s+transformers\b"), "huggingface"),
    (re.compile(r"\b(from|import)\s+huggingface_hub\b"), "huggingface"),
    (re.compile(r"\b(from|import)\s+sentence_transformers\b"), "huggingface"),
    (re.compile(r"\b(from|import)\s+diffusers\b"), "huggingface"),
    (re.compile(r"\b(from|import)\s+peft\b"), "huggingface"),
    (re.compile(r"\b(from|import)\s+trl\b"), "huggingface"),
    (re.compile(r"\b(from|import)\s+datasets\b"), "huggingface"),
    (re.compile(r"\b(from|import)\s+openai\b"), "openai"),
    (re.compile(r"\b(from|import)\s+anthropic\b"), "anthropic"),
    (re.compile(r"\b(from|import)\s+google\.generativeai\b"), "google"),
    (re.compile(r"\b(from|import)\s+vertexai\b"), "google"),
    (re.compile(r"\b(from|import)\s+langchain\b"), "langchain"),
    (re.compile(r"\b(from|import)\s+langchain_openai\b"), "openai"),
    (re.compile(r"\b(from|import)\s+langchain_anthropic\b"), "anthropic"),
    (re.compile(r"\b(from|import)\s+torch\b"), "pytorch"),
    (re.compile(r"\b(from|import)\s+tensorflow\b"), "tensorflow"),
    (re.compile(r"\b(from|import)\s+keras\b"), "keras"),
    (re.compile(r"\b(from|import)\s+sklearn\b"), "sklearn"),
    (re.compile(r"\b(from|import)\s+xgboost\b"), "xgboost"),
    (re.compile(r"\b(from|import)\s+lightgbm\b"), "lightgbm"),
    (re.compile(r"\b(from|import)\s+cohere\b"), "cohere"),
    (re.compile(r"\b(from|import)\s+mistralai\b"), "mistral"),
    (re.compile(r"\b(from|import)\s+together\b"), "together"),
    (re.compile(r"\b(from|import)\s+replicate\b"), "replicate"),
    (re.compile(r"\b(from|import)\s+groq\b"), "groq"),
    (re.compile(r"\b(from|import)\s+boto3\b"), "aws"),         # SageMaker/Bedrock
    (re.compile(r"\b(from|import)\s+sagemaker\b"), "aws"),
    (re.compile(r"\b(from|import)\s+azure\.ai\b"), "azure"),
]

# Providers that call external APIs (data-privacy and availability risk)
_EXTERNAL_API_PROVIDERS = {
    "openai", "anthropic", "google", "cohere",
    "mistral", "together", "replicate", "groq",
    "aws", "azure", "langchain",
}

# ---------------------------------------------------------------------------
# Model ID extraction
# ---------------------------------------------------------------------------

_MODEL_ID_PATTERNS: List[re.Pattern] = [
    # HuggingFace: from_pretrained("model-name")
    re.compile(r'from_pretrained\s*\(\s*["\']([^"\']{3,})["\']'),
    # OpenAI / Anthropic / Groq: model="name"
    re.compile(r'\bmodel\s*=\s*["\']([^"\']{3,})["\']'),
    # pipeline("task", model="name")
    re.compile(r'pipeline\s*\(\s*["\'][^"\']+["\'].*?model\s*=\s*["\']([^"\']+)["\']'),
    # torch.hub.load("org/model", ...)
    re.compile(r'torch\.hub\.load\s*\(\s*["\']([^"\']+)["\']'),
    # GenerativeModel("name") — Google Gemini
    re.compile(r'GenerativeModel\s*\(\s*["\']([^"\']+)["\']'),
    # hf_hub_download / snapshot_download repo_id
    re.compile(r'repo_id\s*=\s*["\']([^"\']+)["\']'),
]

# ---------------------------------------------------------------------------
# License registry  (model-id prefix → license)
# ---------------------------------------------------------------------------

_LICENSE_REGISTRY: Dict[str, str] = {
    # Permissive
    "bert": "apache-2.0",
    "distilbert": "apache-2.0",
    "roberta": "mit",
    "xlm-roberta": "mit",
    "t5": "apache-2.0",
    "gpt2": "mit",
    "mistral": "apache-2.0",
    "mixtral": "apache-2.0",
    "falcon": "apache-2.0",
    "phi": "mit",
    "mpt": "apache-2.0",
    "bloom": "bigscience-bloom-rail-1.0",
    "opt": "mit",
    "flan": "apache-2.0",
    "sentence-transformers": "apache-2.0",
    "all-minilm": "apache-2.0",
    "all-mpnet": "apache-2.0",
    "clip": "mit",
    "whisper": "mit",
    "stable-diffusion": "creativeml-openrail-m",
    "sdxl": "creativeml-openrail-m",
    # Restricted — commercial use requires approval / attribution
    "llama-2": "llama-2-community",
    "llama-3": "llama-3-community",
    "codellama": "llama-2-community",
    "gemma": "gemma-terms",
    "gemma-2": "gemma-terms",
    "qwen": "tongyi-qianwen",
    "baichuan": "baichuan-community",
    "chatglm": "model-specific",
    "yi-": "yi-license",
    # Proprietary (API-only)
    "gpt-3.5": "proprietary",
    "gpt-4": "proprietary",
    "text-davinci": "proprietary",
    "text-embedding": "proprietary",
    "claude": "proprietary",
    "gemini": "proprietary",
    "command": "proprietary",       # Cohere
    "embed-english": "proprietary", # Cohere
}

_RESTRICTED_LICENSES = {
    "llama-2-community", "llama-3-community", "gemma-terms",
    "bigscience-bloom-rail-1.0", "creativeml-openrail-m",
    "tongyi-qianwen", "baichuan-community", "model-specific",
    "yi-license",
}

# ---------------------------------------------------------------------------
# Deprecated / EOL models
# ---------------------------------------------------------------------------

_DEPRECATED_MODELS = {
    "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0613",
    "gpt-4-0314", "gpt-4-0613",
    "text-davinci-003", "text-davinci-002",
    "text-curie-001", "text-babbage-001", "text-ada-001",
    "davinci", "curie", "babbage", "ada",
    "code-davinci-002",
    "claude-1", "claude-instant-1",
    "claude-2.0", "claude-2.1",
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ModelComponent:
    model_id: str
    provider: str
    license: str          # apache-2.0 | mit | proprietary | restricted | unknown
    risk_flags: List[str] # UNKNOWN_LICENSE | RESTRICTED_LICENSE | EXTERNAL_API |
                          # DEPRECATED_MODEL | UNVERSIONED_MODEL
    source_file: str
    source_line: int

    @property
    def is_high_risk(self) -> bool:
        return bool({"UNKNOWN_LICENSE", "RESTRICTED_LICENSE", "DEPRECATED_MODEL"} & set(self.risk_flags))


@dataclass
class SBOMResult:
    components: List[ModelComponent]
    providers_detected: List[str]       # unique provider names found via imports
    unique_model_ids: List[str]
    license_violations: List[ModelComponent]   # restricted + unknown
    risk_score: float                          # 0.0–1.0
    scan_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class AIModelSBOMScanner:
    """Produce a Software Bill of Materials for all AI/ML models in a repo."""

    def scan(self, repo_path: str) -> SBOMResult:
        try:
            return self._scan(Path(repo_path).resolve())
        except Exception as exc:
            return SBOMResult(
                components=[],
                providers_detected=[],
                unique_model_ids=[],
                license_violations=[],
                risk_score=0.0,
                scan_error=str(exc),
            )

    # ------------------------------------------------------------------

    def _scan(self, repo: Path) -> SBOMResult:
        components: List[ModelComponent] = []
        providers_in_file: Dict[str, str] = {}   # fpath → provider (from imports)

        # First pass: collect providers from import lines
        for fpath in self._iter_source_files(repo):
            rel = str(fpath.relative_to(repo))
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines = text.splitlines()
            file_providers: set = set()
            for lineno, line in enumerate(lines, 1):
                for pat, provider in _PROVIDER_IMPORT_PATTERNS:
                    if pat.search(line):
                        file_providers.add(provider)
                        # Also emit a provider-level component (no specific model ID)
                        if provider not in {c.provider for c in components if c.source_file == rel}:
                            comp = self._make_provider_component(provider, rel, lineno)
                            components.append(comp)
            providers_in_file[rel] = file_providers  # type: ignore[assignment]

        # Second pass: extract model IDs from all source files
        for fpath in self._iter_source_files(repo):
            rel = str(fpath.relative_to(repo))
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                for pat in _MODEL_ID_PATTERNS:
                    m = pat.search(line)
                    if not m:
                        continue
                    model_id = m.group(1).strip()
                    if not self._looks_like_model_id(model_id):
                        continue
                    provider = self._infer_provider(model_id, providers_in_file.get(rel, set()))
                    lic = self._lookup_license(model_id)
                    flags = self._compute_flags(model_id, provider, lic)
                    comp = ModelComponent(
                        model_id=model_id,
                        provider=provider,
                        license=lic,
                        risk_flags=flags,
                        source_file=rel,
                        source_line=lineno,
                    )
                    # Deduplicate: same model_id + file
                    if not any(c.model_id == model_id and c.source_file == rel for c in components):
                        components.append(comp)

        providers_detected = sorted({c.provider for c in components if c.provider != "unknown"})
        unique_ids = sorted({c.model_id for c in components if c.model_id})
        violations = [c for c in components if c.is_high_risk]
        risk_score = self._compute_risk_score(components)

        return SBOMResult(
            components=components,
            providers_detected=providers_detected,
            unique_model_ids=unique_ids,
            license_violations=violations,
            risk_score=risk_score,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _iter_source_files(self, repo: Path):
        for fpath in repo.rglob("*"):
            if not fpath.is_file():
                continue
            if any(p in _SKIP_DIRS for p in fpath.parts):
                continue
            if fpath.suffix.lower() in _SOURCE_EXTS:
                yield fpath

    def _make_provider_component(self, provider: str, source_file: str, lineno: int) -> ModelComponent:
        lic = "proprietary" if provider in _EXTERNAL_API_PROVIDERS else "varies"
        flags: List[str] = []
        if provider in _EXTERNAL_API_PROVIDERS:
            flags.append("EXTERNAL_API")
        return ModelComponent(
            model_id=f"[{provider}-sdk]",
            provider=provider,
            license=lic,
            risk_flags=flags,
            source_file=source_file,
            source_line=lineno,
        )

    def _looks_like_model_id(self, value: str) -> bool:
        """Reject env-var names, pure integers, very short tokens, Python identifiers."""
        if len(value) < 3 or len(value) > 120:
            return False
        # All-caps env var or pure uppercase constant
        if re.match(r'^[A-Z][A-Z_0-9]{3,}$', value):
            return False
        # Looks like a Python class name / single word with no separator
        if re.match(r'^[A-Z][a-zA-Z]+$', value) and '-' not in value and '/' not in value:
            return False
        # Looks like a version string or number
        if re.match(r'^\d', value):
            return False
        return True

    def _infer_provider(self, model_id: str, file_providers: set) -> str:
        mid_lower = model_id.lower()
        if any(x in mid_lower for x in ("gpt-", "text-davinci", "text-embedding", "davinci", "curie")):
            return "openai"
        if "claude" in mid_lower:
            return "anthropic"
        if any(x in mid_lower for x in ("gemini", "gemma", "palm")):
            return "google"
        if any(x in mid_lower for x in ("command-", "embed-english")):
            return "cohere"
        if "/" in model_id:
            return "huggingface"  # org/model format
        # Fall back to what's imported in the same file
        for p in ("openai", "anthropic", "google", "cohere", "huggingface", "pytorch"):
            if p in file_providers:
                return p
        return "unknown"

    def _lookup_license(self, model_id: str) -> str:
        mid_lower = model_id.lower()
        for prefix, lic in _LICENSE_REGISTRY.items():
            if mid_lower.startswith(prefix) or prefix in mid_lower:
                return lic
        return "unknown"

    def _compute_flags(self, model_id: str, provider: str, lic: str) -> List[str]:
        flags: List[str] = []
        if lic == "unknown":
            flags.append("UNKNOWN_LICENSE")
        elif lic in _RESTRICTED_LICENSES:
            flags.append("RESTRICTED_LICENSE")
        if provider in _EXTERNAL_API_PROVIDERS:
            flags.append("EXTERNAL_API")
        if model_id.lower() in _DEPRECATED_MODELS:
            flags.append("DEPRECATED_MODEL")
        # No version pin: pure name with no version suffix (e.g. "gpt-4" vs "gpt-4-turbo-2024-04-09")
        if not re.search(r'[-_:@](v?\d[\d.]*|latest|stable|snapshot)$', model_id, re.IGNORECASE):
            flags.append("UNVERSIONED_MODEL")
        return flags

    def _compute_risk_score(self, components: List[ModelComponent]) -> float:
        if not components:
            return 0.0
        weights = {
            "UNKNOWN_LICENSE": 0.6,
            "RESTRICTED_LICENSE": 0.5,
            "EXTERNAL_API": 0.3,
            "DEPRECATED_MODEL": 0.8,
            "UNVERSIONED_MODEL": 0.2,
        }
        # Use unique model IDs for scoring (not per-file duplicates)
        seen: set = set()
        total = 0.0
        for c in components:
            key = (c.model_id, frozenset(c.risk_flags))
            if key in seen:
                continue
            seen.add(key)
            score = max((weights.get(f, 0.0) for f in c.risk_flags), default=0.0)
            total += score
        # Cap at 1.0; dampen with sqrt to avoid saturation on large repos
        import math
        return round(min(1.0, math.sqrt(total / max(len(seen), 1)) * 0.7), 3)
