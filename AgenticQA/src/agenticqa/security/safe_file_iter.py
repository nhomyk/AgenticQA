"""Safe file iteration for security scanners — prevents OOM on large repos.

Provides:
  - ``iter_source_files()`` — yields source files with count/size limits
  - ``MAX_FILES`` (default 50_000) — hard cap on files per scan
  - ``MAX_FILE_SIZE`` (default 10 MB) — skip files larger than this
  - ``SKIP_DIRS`` — unified set of directories to skip

All security scanners should use this instead of raw ``rglob("*")``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator, Optional, Set

# ── Defaults ──────────────────────────────────────────────────────────────────

MAX_FILES: int = 50_000
MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB

SKIP_DIRS: Set[str] = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", "DerivedData", "vendor", "target",
    ".gradle", ".mvn", ".next", "out", "coverage", ".nyc_output",
    ".tox", ".mypy_cache", ".pytest_cache", ".eggs", "egg-info",
    ".terraform", ".serverless", "bower_components",
}

SOURCE_EXTENSIONS: Set[str] = {
    ".py", ".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs",
    ".swift", ".go", ".java", ".kt", ".rs", ".rb",
    ".yaml", ".yml", ".json",
}


def iter_source_files(
    root: Path,
    *,
    extensions: Optional[Set[str]] = None,
    skip_dirs: Optional[Set[str]] = None,
    max_files: int = MAX_FILES,
    max_file_size: int = MAX_FILE_SIZE,
) -> Iterator[Path]:
    """Yield source files under *root* with safety limits.

    Args:
        root: Repository root directory.
        extensions: File extensions to include (default: SOURCE_EXTENSIONS).
        skip_dirs: Directory names to skip (default: SKIP_DIRS).
        max_files: Stop after yielding this many files.
        max_file_size: Skip individual files larger than this (bytes).

    Yields:
        ``Path`` objects for each matching source file.
    """
    exts = extensions or SOURCE_EXTENSIONS
    dirs_to_skip = skip_dirs or SKIP_DIRS
    count = 0

    for fpath in root.rglob("*"):
        if count >= max_files:
            break
        if not fpath.is_file():
            continue
        if any(part in dirs_to_skip for part in fpath.parts):
            continue
        if fpath.suffix.lower() not in exts:
            continue
        # Skip oversized files (e.g., minified bundles, binaries with wrong ext)
        try:
            if fpath.stat().st_size > max_file_size:
                continue
        except OSError:
            continue
        count += 1
        yield fpath


def safe_read_text(fpath: Path, max_size: int = MAX_FILE_SIZE) -> Optional[str]:
    """Read file text safely — returns None if too large or unreadable."""
    try:
        if fpath.stat().st_size > max_size:
            return None
        return fpath.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return None
