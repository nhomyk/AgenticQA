"""
Blast Radius Analyzer — static import graph analysis.

Given a list of changed files (e.g., from a PR diff), determines which
other modules are directly or transitively affected and produces a risk score.

Supports Python (import X, from X import Y) and TypeScript/JavaScript
(import ... from './X', require('./X')). No subprocess — pure Python + pathlib.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Critical-path keyword patterns (auth / payment / security etc.)
# ---------------------------------------------------------------------------
_CRITICAL_KEYWORDS = frozenset(
    [
        "auth", "login", "password", "payment", "billing", "secret",
        "database", "db", "admin", "security", "crypto", "token",
        "permission",
    ]
)

# Source extensions to parse for imports
_PYTHON_EXTS = {".py"}
_TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
_ALL_EXTS = _PYTHON_EXTS | _TS_EXTS

_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build"}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BlastRadiusResult:
    changed_files: List[str]
    directly_affected: List[str]
    transitively_affected: List[str]
    critical_paths: List[str]
    total_affected: int
    blast_radius_score: float   # 0-100
    risk_level: str             # low | medium | high | critical
    summary: str

    def to_dict(self) -> dict:
        return {
            "changed_files": self.changed_files,
            "directly_affected": self.directly_affected,
            "transitively_affected": self.transitively_affected,
            "critical_paths": self.critical_paths,
            "total_affected": self.total_affected,
            "blast_radius_score": self.blast_radius_score,
            "risk_level": self.risk_level,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class BlastRadiusAnalyzer:
    """Analyze which modules are affected by a set of changed files."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, repo_path: str, changed_files: List[str]) -> BlastRadiusResult:
        root = Path(repo_path).resolve()
        changed_set: Set[str] = {str(Path(f)) for f in changed_files}

        if not changed_files:
            return BlastRadiusResult(
                changed_files=[],
                directly_affected=[],
                transitively_affected=[],
                critical_paths=[],
                total_affected=0,
                blast_radius_score=0.0,
                risk_level="low",
                summary="No changed files provided.",
            )

        # Build full import graph: file -> set of files it imports
        graph = self._build_import_graph(root)
        total_files = len(graph)

        # Find directly and transitively affected files
        direct, transitive = self._find_affected(graph, changed_set)

        # Remove changed files from affected lists
        direct = sorted(direct - changed_set)
        transitive = sorted(transitive - changed_set - set(direct))

        # Critical path detection
        critical_paths = self._detect_critical_paths(changed_files, root)

        # Score
        total_affected = len(direct) + len(transitive)
        score = min(
            100.0,
            (len(direct) * 3 + len(transitive) * 1) / max(total_files, 1) * 100,
        )

        # Risk level
        if score >= 75:
            risk_level = "critical"
        elif score >= 40:
            risk_level = "high"
        elif score >= 15:
            risk_level = "medium"
        else:
            risk_level = "low"

        summary = (
            f"{len(changed_files)} file(s) changed; "
            f"{len(direct)} directly affected, "
            f"{len(transitive)} transitively affected. "
            f"Blast radius score: {score:.1f}/100 ({risk_level})."
        )
        if critical_paths:
            summary += f" {len(critical_paths)} critical path(s) detected."

        return BlastRadiusResult(
            changed_files=sorted(changed_files),
            directly_affected=direct,
            transitively_affected=transitive,
            critical_paths=sorted(critical_paths),
            total_affected=total_affected,
            blast_radius_score=round(score, 2),
            risk_level=risk_level,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Import graph construction
    # ------------------------------------------------------------------

    def _build_import_graph(self, root: Path) -> Dict[str, Set[str]]:
        """Return a mapping of file_path -> set of files it imports."""
        graph: Dict[str, Set[str]] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix not in _ALL_EXTS:
                continue
            key = str(path.relative_to(root))
            graph[key] = self._parse_imports(path, root)
        return graph

    def _parse_imports(self, path: Path, root: Path) -> Set[str]:
        """Extract imported file references from a source file."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return set()

        imported: Set[str] = set()

        if path.suffix in _PYTHON_EXTS:
            imported |= self._parse_python_imports(content, path, root)
        else:
            imported |= self._parse_ts_imports(content, path, root)

        return imported

    # -- Python --

    def _parse_python_imports(self, content: str, source: Path, root: Path) -> Set[str]:
        refs: Set[str] = set()
        # "import foo.bar" and "from foo.bar import baz"
        pattern = re.compile(
            r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))",
            re.MULTILINE,
        )
        for m in pattern.finditer(content):
            module_str = m.group(1) or m.group(2)
            for mod in module_str.split(","):
                mod = mod.strip().split(" ")[0]  # "X as Y" -> "X"
                if not mod:
                    continue
                resolved = self._resolve_python_module(mod, source, root)
                if resolved:
                    refs.add(resolved)
        return refs

    def _resolve_python_module(self, module: str, source: Path, root: Path) -> Optional[str]:
        """Try to resolve a dotted module name to a file path relative to root."""
        parts = module.split(".")
        # Try from root
        for candidate in [
            root / Path(*parts).with_suffix(".py"),
            root / Path(*parts) / "__init__.py",
        ]:
            if candidate.exists():
                return str(candidate.relative_to(root))
        # Try relative to source dir
        source_dir = source.parent
        for candidate in [
            source_dir / Path(*parts).with_suffix(".py"),
            source_dir / Path(*parts) / "__init__.py",
        ]:
            if candidate.exists():
                return str(candidate.relative_to(root))
        return None

    # -- TypeScript / JavaScript --

    def _parse_ts_imports(self, content: str, source: Path, root: Path) -> Set[str]:
        refs: Set[str] = set()
        # import ... from './path' or import('...')
        from_pattern = re.compile(
            r"""(?:import|from)\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
            re.MULTILINE,
        )
        for m in from_pattern.finditer(content):
            spec = m.group(1) or m.group(2)
            if not spec.startswith(("./", "../")):
                continue
            resolved = self._resolve_ts_import(spec, source, root)
            if resolved:
                refs.add(resolved)
        return refs

    def _resolve_ts_import(self, spec: str, source: Path, root: Path) -> Optional[str]:
        base = (source.parent / spec).resolve()
        candidates = [
            base.with_suffix(".ts"),
            base.with_suffix(".tsx"),
            base.with_suffix(".js"),
            base.with_suffix(".jsx"),
            base / "index.ts",
            base / "index.js",
            base,  # exact
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                try:
                    return str(c.relative_to(root))
                except ValueError:
                    pass
        return None

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def _find_affected(
        self, graph: Dict[str, Set[str]], changed: Set[str]
    ) -> tuple:
        """BFS to find directly and transitively affected files.

        'Affected' means a file *imports* one of the changed files
        (reverse dependency direction).
        """
        # Reverse graph: file -> set of files that import it
        reverse: Dict[str, Set[str]] = {k: set() for k in graph}
        for importer, imports in graph.items():
            for dep in imports:
                if dep not in reverse:
                    reverse[dep] = set()
                reverse[dep].add(importer)

        directly: Set[str] = set()
        for changed_file in changed:
            # Normalize to relative path if needed
            for key in graph:
                if key == changed_file or key.endswith(changed_file) or changed_file.endswith(key):
                    directly |= reverse.get(key, set())

        transitively: Set[str] = set()
        frontier = set(directly)
        visited: Set[str] = set(directly) | changed
        while frontier:
            next_frontier: Set[str] = set()
            for f in frontier:
                for importer in reverse.get(f, set()):
                    if importer not in visited:
                        visited.add(importer)
                        transitively.add(importer)
                        next_frontier.add(importer)
            frontier = next_frontier

        return directly, transitively

    # ------------------------------------------------------------------
    # Critical path detection
    # ------------------------------------------------------------------

    def _detect_critical_paths(self, changed_files: List[str], root: Path) -> List[str]:
        critical: List[str] = []
        for f in changed_files:
            lower = f.lower()
            if any(kw in lower for kw in _CRITICAL_KEYWORDS):
                critical.append(f)
                continue
            # Also scan content of changed file for critical keywords
            full_path = root / f
            if full_path.exists():
                try:
                    text = full_path.read_text(encoding="utf-8", errors="ignore").lower()
                    if any(kw in text for kw in _CRITICAL_KEYWORDS):
                        critical.append(f)
                except OSError:
                    pass
        return list(set(critical))
