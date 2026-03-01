"""Sandboxed file manager for the AgenticQA workspace.

All file operations are confined to WORKSPACE_ROOT (default ~/.agenticqa/workspace/files/).
Path traversal outside the sandbox is blocked at every entry point.
"""
from __future__ import annotations

import mimetypes
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_WORKSPACE_ROOT = Path.home() / ".agenticqa" / "workspace" / "files"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
MAX_WORKSPACE_SIZE = 500 * 1024 * 1024  # 500 MB total
MAX_FILES = 10_000

# Extensions that may never be written (executable, system, etc.)
BLOCKED_EXTENSIONS = frozenset({
    ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".com", ".scr",
    ".msi", ".vbs", ".ps1", ".sh", ".bash", ".csh", ".ksh",
    ".app", ".deb", ".rpm", ".dmg", ".iso",
})

# ── Result types ─────────────────────────────────────────────────────────────


@dataclass
class FileEntry:
    """Metadata for a single file or directory."""
    name: str
    path: str  # relative to workspace root
    is_dir: bool
    size: int = 0
    modified: float = 0.0
    mime_type: str = ""


@dataclass
class FileOpResult:
    """Result of a file operation."""
    success: bool
    action: str  # list, read, write, delete, mkdir, move, copy
    path: str = ""
    error: Optional[str] = None
    data: Any = None  # payload (file content, listing, etc.)
    blocked_reason: Optional[str] = None


# ── Sandbox manager ──────────────────────────────────────────────────────────


class SandboxedFileManager:
    """File operations confined to a sandbox root directory.

    Every public method resolves the target path and verifies it lives
    inside ``root``.  Traversal attempts raise immediately.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else DEFAULT_WORKSPACE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    # ── helpers ───────────────────────────────────────────────────────────

    def _resolve(self, rel: str) -> Path:
        """Resolve *rel* inside the sandbox, blocking any escape."""
        # Normalise and strip leading separators so join is predictable
        cleaned = rel.lstrip("/").lstrip("\\")
        target = (self.root / cleaned).resolve()
        sandbox = self.root.resolve()
        if not str(target).startswith(str(sandbox)):
            raise PermissionError(
                f"Path traversal blocked: '{rel}' resolves outside sandbox"
            )
        return target

    def _workspace_size(self) -> int:
        total = 0
        for dirpath, _dirs, files in os.walk(self.root):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
        return total

    def _file_count(self) -> int:
        count = 0
        for _dirpath, _dirs, files in os.walk(self.root):
            count += len(files)
        return count

    def _relative(self, abspath: Path) -> str:
        try:
            return str(abspath.relative_to(self.root.resolve()))
        except ValueError:
            return str(abspath)

    # ── public API ────────────────────────────────────────────────────────

    def list_dir(self, rel: str = "") -> FileOpResult:
        """List files and directories at *rel* (default: root)."""
        try:
            target = self._resolve(rel)
        except PermissionError as exc:
            return FileOpResult(success=False, action="list", path=rel,
                                error=str(exc), blocked_reason="path_traversal")

        if not target.is_dir():
            return FileOpResult(success=False, action="list", path=rel,
                                error="Not a directory")

        entries: List[FileEntry] = []
        try:
            for child in sorted(target.iterdir()):
                stat = child.stat()
                mime = mimetypes.guess_type(child.name)[0] or ""
                entries.append(FileEntry(
                    name=child.name,
                    path=self._relative(child.resolve()),
                    is_dir=child.is_dir(),
                    size=stat.st_size if child.is_file() else 0,
                    modified=stat.st_mtime,
                    mime_type=mime,
                ))
        except OSError as exc:
            return FileOpResult(success=False, action="list", path=rel,
                                error=str(exc))

        return FileOpResult(success=True, action="list", path=rel, data=entries)

    def read_file(self, rel: str) -> FileOpResult:
        """Read a text file and return its content."""
        try:
            target = self._resolve(rel)
        except PermissionError as exc:
            return FileOpResult(success=False, action="read", path=rel,
                                error=str(exc), blocked_reason="path_traversal")

        if not target.is_file():
            return FileOpResult(success=False, action="read", path=rel,
                                error="File not found")

        if target.stat().st_size > MAX_FILE_SIZE:
            return FileOpResult(success=False, action="read", path=rel,
                                error=f"File exceeds {MAX_FILE_SIZE} byte limit")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return FileOpResult(success=False, action="read", path=rel,
                                error=str(exc))

        return FileOpResult(success=True, action="read", path=rel, data=content)

    def write_file(self, rel: str, content: str) -> FileOpResult:
        """Write *content* to a text file inside the sandbox."""
        try:
            target = self._resolve(rel)
        except PermissionError as exc:
            return FileOpResult(success=False, action="write", path=rel,
                                error=str(exc), blocked_reason="path_traversal")

        # Block dangerous extensions
        ext = target.suffix.lower()
        if ext in BLOCKED_EXTENSIONS:
            return FileOpResult(success=False, action="write", path=rel,
                                error=f"Extension '{ext}' is blocked",
                                blocked_reason="blocked_extension")

        # Size guard
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > MAX_FILE_SIZE:
            return FileOpResult(success=False, action="write", path=rel,
                                error=f"Content exceeds {MAX_FILE_SIZE} byte limit")

        # Workspace capacity guard
        current_size = self._workspace_size()
        if current_size + len(content_bytes) > MAX_WORKSPACE_SIZE:
            return FileOpResult(success=False, action="write", path=rel,
                                error="Workspace storage limit exceeded",
                                blocked_reason="workspace_full")

        if self._file_count() >= MAX_FILES and not target.exists():
            return FileOpResult(success=False, action="write", path=rel,
                                error="Workspace file count limit reached",
                                blocked_reason="too_many_files")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return FileOpResult(success=False, action="write", path=rel,
                                error=str(exc))

        return FileOpResult(success=True, action="write", path=rel)

    def delete_file(self, rel: str) -> FileOpResult:
        """Delete a file (not directory) inside the sandbox."""
        try:
            target = self._resolve(rel)
        except PermissionError as exc:
            return FileOpResult(success=False, action="delete", path=rel,
                                error=str(exc), blocked_reason="path_traversal")

        if not target.exists():
            return FileOpResult(success=False, action="delete", path=rel,
                                error="File not found")

        if target.is_dir():
            return FileOpResult(success=False, action="delete", path=rel,
                                error="Cannot delete directories via delete_file; use delete_dir")

        try:
            target.unlink()
        except OSError as exc:
            return FileOpResult(success=False, action="delete", path=rel,
                                error=str(exc))

        return FileOpResult(success=True, action="delete", path=rel)

    def delete_dir(self, rel: str) -> FileOpResult:
        """Delete an empty directory inside the sandbox."""
        try:
            target = self._resolve(rel)
        except PermissionError as exc:
            return FileOpResult(success=False, action="delete_dir", path=rel,
                                error=str(exc), blocked_reason="path_traversal")

        if not target.is_dir():
            return FileOpResult(success=False, action="delete_dir", path=rel,
                                error="Not a directory")

        if target.resolve() == self.root.resolve():
            return FileOpResult(success=False, action="delete_dir", path=rel,
                                error="Cannot delete workspace root",
                                blocked_reason="root_protected")

        if any(target.iterdir()):
            return FileOpResult(success=False, action="delete_dir", path=rel,
                                error="Directory is not empty")

        try:
            target.rmdir()
        except OSError as exc:
            return FileOpResult(success=False, action="delete_dir", path=rel,
                                error=str(exc))

        return FileOpResult(success=True, action="delete_dir", path=rel)

    def mkdir(self, rel: str) -> FileOpResult:
        """Create a directory inside the sandbox."""
        try:
            target = self._resolve(rel)
        except PermissionError as exc:
            return FileOpResult(success=False, action="mkdir", path=rel,
                                error=str(exc), blocked_reason="path_traversal")

        if target.exists():
            return FileOpResult(success=True, action="mkdir", path=rel)

        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return FileOpResult(success=False, action="mkdir", path=rel,
                                error=str(exc))

        return FileOpResult(success=True, action="mkdir", path=rel)

    def move(self, src_rel: str, dst_rel: str) -> FileOpResult:
        """Move/rename a file inside the sandbox."""
        try:
            src = self._resolve(src_rel)
            dst = self._resolve(dst_rel)
        except PermissionError as exc:
            return FileOpResult(success=False, action="move",
                                error=str(exc), blocked_reason="path_traversal")

        if not src.exists():
            return FileOpResult(success=False, action="move", path=src_rel,
                                error="Source not found")

        ext = dst.suffix.lower()
        if ext in BLOCKED_EXTENSIONS:
            return FileOpResult(success=False, action="move", path=dst_rel,
                                error=f"Extension '{ext}' is blocked",
                                blocked_reason="blocked_extension")

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        except OSError as exc:
            return FileOpResult(success=False, action="move",
                                error=str(exc))

        return FileOpResult(success=True, action="move", path=dst_rel)

    def get_workspace_info(self) -> Dict[str, Any]:
        """Return workspace usage statistics."""
        return {
            "root": str(self.root),
            "file_count": self._file_count(),
            "total_size_bytes": self._workspace_size(),
            "max_file_size": MAX_FILE_SIZE,
            "max_workspace_size": MAX_WORKSPACE_SIZE,
            "max_files": MAX_FILES,
        }
