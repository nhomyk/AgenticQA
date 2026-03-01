"""Path sanitization — jail repo_path parameters to allowed directories.

Prevents path traversal attacks (CWE-22) by resolving symlinks and verifying
the resolved path falls within an allowed root.

Usage:
    from agenticqa.security.path_sanitizer import sanitize_repo_path

    safe = sanitize_repo_path("/tmp/../etc/passwd")  # raises ValueError
    safe = sanitize_repo_path("/tmp/my-repo")         # returns "/tmp/my-repo"
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence

# Default allowed roots — CWD, /tmp, and home directory
_DEFAULT_ALLOWED_ROOTS: Optional[Sequence[str]] = None


def _get_allowed_roots() -> list[str]:
    """Return the list of allowed root directories.

    Reads ``AGENTICQA_ALLOWED_ROOTS`` (colon-separated) if set,
    otherwise falls back to CWD + /tmp + $HOME.
    """
    env = os.environ.get("AGENTICQA_ALLOWED_ROOTS", "")
    if env:
        return [str(Path(p).resolve()) for p in env.split(":") if p.strip()]

    roots = [
        str(Path.cwd().resolve()),
        str(Path("/tmp").resolve()),  # macOS: /tmp → /private/tmp
    ]
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if home:
        roots.append(str(Path(home).resolve()))

    # GitHub Actions / CI runner paths
    gh_workspace = os.environ.get("GITHUB_WORKSPACE")
    if gh_workspace:
        roots.append(str(Path(gh_workspace).resolve()))

    return roots


def sanitize_repo_path(
    repo_path: str,
    *,
    allowed_roots: Optional[Sequence[str]] = None,
) -> str:
    """Resolve and validate *repo_path* against allowed roots.

    Args:
        repo_path: Path supplied by the caller (query param, JSON body, etc.)
        allowed_roots: Override the allowed root directories.
            Defaults to ``AGENTICQA_ALLOWED_ROOTS`` env var, or CWD + /tmp + $HOME.

    Returns:
        The resolved, absolute path string.

    Raises:
        ValueError: If the resolved path escapes all allowed roots.
    """
    resolved = str(Path(repo_path).expanduser().resolve())

    roots = allowed_roots or _get_allowed_roots()
    for root in roots:
        root_resolved = str(Path(root).resolve())
        if resolved == root_resolved or resolved.startswith(root_resolved + os.sep):
            return resolved

    raise ValueError(
        f"Path '{repo_path}' resolves to '{resolved}' which is outside "
        f"allowed roots: {list(roots)}"
    )
