"""
Coverage Mapper

Walks a repository and determines which source files already have tests
and which do not. Works across Python, TypeScript, JavaScript, Swift, Go,
and other languages by matching test-file naming conventions.

Test file patterns recognised
------------------------------
Python:      test_*.py  |  *_test.py  |  tests/**/*.py
TypeScript:  *.test.ts  |  *.spec.ts  |  __tests__/**/*.ts
JavaScript:  *.test.js  |  *.spec.js  |  __tests__/**/*.js
TSX/JSX:     *.test.tsx |  *.spec.tsx |  *.test.jsx | *.spec.jsx
Vue:         *.spec.ts  (inside __tests__ or alongside component)
Go:          *_test.go
Swift:       *Tests.swift  |  *Spec.swift
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


# ── Constants ──────────────────────────────────────────────────────────────────

_SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".vue", ".svelte", ".go", ".swift", ".rb", ".java", ".kt",
}

_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", "DerivedData", "vendor", "target",
    ".tox", "coverage", ".nyc_output", ".cache",
}

_TEST_PATTERNS = [
    # Python
    re.compile(r"^test_.*\.py$"),
    re.compile(r"^.*_test\.py$"),
    # JS/TS
    re.compile(r"^.*\.test\.(ts|tsx|js|jsx)$"),
    re.compile(r"^.*\.spec\.(ts|tsx|js|jsx)$"),
    # Go
    re.compile(r"^.*_test\.go$"),
    # Swift
    re.compile(r"^.*Tests\.swift$"),
    re.compile(r"^.*Spec\.swift$"),
    # Ruby
    re.compile(r"^.*_spec\.rb$"),
    re.compile(r"^.*_test\.rb$"),
    # Java/Kotlin
    re.compile(r"^.*Test\.(java|kt)$"),
    re.compile(r"^.*Tests\.(java|kt)$"),
]

_TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "specs", "test_suite"}


def _is_test_file(path: Path) -> bool:
    name = path.name
    # Parent directory is a test directory
    if any(p.name.lower() in _TEST_DIR_NAMES for p in path.parents):
        return path.suffix in _SOURCE_EXTENSIONS
    # File name matches a test pattern
    return any(pat.match(name) for pat in _TEST_PATTERNS)


def _stem_variants(stem: str) -> Set[str]:
    """Return multiple lowercased stem variants to match against."""
    s = stem.lower()
    variants = {s}
    # strip common suffixes added to source names to make test names
    for suffix in ("service", "controller", "handler", "util", "helper",
                   "model", "view", "component", "page", "api", "client"):
        if s.endswith(suffix):
            variants.add(s[: -len(suffix)])
    return variants


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class LanguageCoverage:
    language: str
    total: int
    covered: int
    uncovered: int

    @property
    def ratio(self) -> float:
        return self.covered / self.total if self.total else 0.0


@dataclass
class CoverageMap:
    repo_path: str
    total_source_files: int
    covered_files: List[str]        # source files with at least one matching test
    uncovered_files: List[str]      # source files with no matching test
    test_files: List[str]           # all detected test files
    by_language: Dict[str, LanguageCoverage] = field(default_factory=dict)
    high_risk_uncovered: List[str] = field(default_factory=list)  # set by caller

    @property
    def coverage_ratio(self) -> float:
        if self.total_source_files == 0:
            return 0.0
        return len(self.covered_files) / self.total_source_files

    @property
    def coverage_pct(self) -> float:
        return round(self.coverage_ratio * 100, 1)

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "total_source_files": self.total_source_files,
            "covered_count": len(self.covered_files),
            "uncovered_count": len(self.uncovered_files),
            "test_file_count": len(self.test_files),
            "coverage_pct": self.coverage_pct,
            "high_risk_uncovered_count": len(self.high_risk_uncovered),
            "by_language": {
                lang: {
                    "total": lc.total,
                    "covered": lc.covered,
                    "coverage_pct": round(lc.ratio * 100, 1),
                }
                for lang, lc in self.by_language.items()
            },
            "uncovered_files": self.uncovered_files[:50],  # cap for API response
            "high_risk_uncovered": self.high_risk_uncovered,
        }


# ── Mapper ─────────────────────────────────────────────────────────────────────

class CoverageMapper:
    """Map source files to test files across a repository."""

    def scan(self, repo_path: str) -> CoverageMap:
        root = Path(repo_path).resolve()
        source_files: List[Path] = []
        test_files: List[Path] = []

        for path in root.rglob("*"):
            if path.is_dir():
                continue
            if any(skip in path.parts for skip in _SKIP_DIRS):
                continue
            if path.suffix not in _SOURCE_EXTENSIONS:
                continue
            if _is_test_file(path):
                test_files.append(path)
            else:
                source_files.append(path)

        # Build lookup: stem variants → test file paths
        test_stems: Dict[str, List[Path]] = {}
        for tf in test_files:
            # Strip test prefix/suffix from test file name
            name = tf.stem.lower()
            for prefix in ("test_", "spec_"):
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    break
            for suffix in ("_test", "_spec", "test", "spec", "tests", "specs"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            name = name.rstrip(".")  # handle Button.spec → button (after stripping spec)
            test_stems.setdefault(name, []).append(tf)

        covered: List[str] = []
        uncovered: List[str] = []
        lang_stats: Dict[str, Dict[str, int]] = {}

        for src in source_files:
            lang = self._language(src)
            lang_stats.setdefault(lang, {"total": 0, "covered": 0})
            lang_stats[lang]["total"] += 1

            rel = str(src.relative_to(root))
            matched = False

            for variant in _stem_variants(src.stem):
                if variant in test_stems:
                    matched = True
                    break

            if matched:
                covered.append(rel)
                lang_stats[lang]["covered"] += 1
            else:
                uncovered.append(rel)

        by_language = {
            lang: LanguageCoverage(
                language=lang,
                total=s["total"],
                covered=s["covered"],
                uncovered=s["total"] - s["covered"],
            )
            for lang, s in lang_stats.items()
        }

        return CoverageMap(
            repo_path=str(root),
            total_source_files=len(source_files),
            covered_files=covered,
            uncovered_files=uncovered,
            test_files=[str(tf.relative_to(root)) for tf in test_files],
            by_language=by_language,
        )

    def _language(self, path: Path) -> str:
        return {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".vue": "vue",
            ".svelte": "svelte",
            ".go": "go",
            ".swift": "swift",
            ".rb": "ruby",
            ".java": "java",
            ".kt": "kotlin",
        }.get(path.suffix, path.suffix.lstrip(".") or "unknown")
