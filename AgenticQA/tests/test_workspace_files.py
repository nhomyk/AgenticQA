"""Tests for the sandboxed file manager.

Validates:
  - Path traversal prevention
  - File size/count limits
  - Extension blocking
  - CRUD operations (list, read, write, delete, mkdir, move)
  - Workspace capacity guard
"""
import pytest
from pathlib import Path

from agenticqa.workspace.file_manager import (
    SandboxedFileManager,
    BLOCKED_EXTENSIONS,
    MAX_FILE_SIZE,
)


@pytest.fixture
def fm(tmp_path):
    """File manager with a temporary sandbox root."""
    return SandboxedFileManager(root=tmp_path)


# ── Path traversal prevention ────────────────────────────────────────────────


@pytest.mark.unit
def test_traversal_blocked_dot_dot(fm):
    """Path traversal with ../.. is blocked."""
    result = fm.read_file("../../etc/passwd")
    assert not result.success
    assert result.blocked_reason == "path_traversal"


@pytest.mark.unit
def test_traversal_blocked_absolute(fm):
    """Absolute paths are normalised — only sandbox-interior paths pass."""
    result = fm.read_file("/etc/passwd")
    # /etc/passwd doesn't exist inside the sandbox
    assert not result.success


@pytest.mark.unit
def test_traversal_blocked_write(fm):
    """Write with path traversal is blocked."""
    result = fm.write_file("../../../tmp/evil.txt", "pwned")
    assert not result.success
    assert result.blocked_reason == "path_traversal"


@pytest.mark.unit
def test_traversal_blocked_delete(fm):
    """Delete with path traversal is blocked."""
    result = fm.delete_file("../../etc/hosts")
    assert not result.success
    assert result.blocked_reason == "path_traversal"


# ── Extension blocking ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_blocked_extension_exe(fm):
    """Cannot write .exe files."""
    result = fm.write_file("malware.exe", "MZ...")
    assert not result.success
    assert result.blocked_reason == "blocked_extension"


@pytest.mark.unit
def test_blocked_extension_sh(fm):
    """Cannot write .sh files."""
    result = fm.write_file("deploy.sh", "#!/bin/bash\nrm -rf /")
    assert not result.success
    assert result.blocked_reason == "blocked_extension"


@pytest.mark.unit
def test_blocked_extension_move(fm):
    """Cannot move a file to a blocked extension."""
    fm.write_file("safe.txt", "hello")
    result = fm.move("safe.txt", "evil.exe")
    assert not result.success
    assert result.blocked_reason == "blocked_extension"


@pytest.mark.unit
def test_allowed_extensions(fm):
    """Common text extensions are allowed."""
    for ext in [".txt", ".md", ".py", ".json", ".yaml", ".csv"]:
        result = fm.write_file(f"test{ext}", "content")
        assert result.success, f"Extension {ext} should be allowed"


# ── File size limits ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_write_size_limit(fm):
    """Cannot write content exceeding MAX_FILE_SIZE."""
    big = "x" * (MAX_FILE_SIZE + 1)
    result = fm.write_file("huge.txt", big)
    assert not result.success
    assert "limit" in result.error.lower()


@pytest.mark.unit
def test_read_size_limit(fm):
    """Cannot read files exceeding MAX_FILE_SIZE."""
    # Write directly to bypass the manager's own size check
    target = fm.root / "huge.txt"
    target.write_text("x" * (MAX_FILE_SIZE + 1))
    result = fm.read_file("huge.txt")
    assert not result.success
    assert "limit" in result.error.lower()


# ── Workspace capacity guard ─────────────────────────────────────────────────


@pytest.mark.unit
def test_file_count_limit(tmp_path):
    """Cannot create more than MAX_FILES files."""
    fm = SandboxedFileManager(root=tmp_path)
    # Create files up to the limit — use a low limit for speed
    from unittest.mock import patch
    with patch("agenticqa.workspace.file_manager.MAX_FILES", 3):
        fm.write_file("a.txt", "1")
        fm.write_file("b.txt", "2")
        fm.write_file("c.txt", "3")
        result = fm.write_file("d.txt", "4")
        assert not result.success
        assert result.blocked_reason == "too_many_files"


# ── CRUD operations ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_write_and_read(fm):
    """Write a file and read it back."""
    fm.write_file("hello.txt", "Hello, workspace!")
    result = fm.read_file("hello.txt")
    assert result.success
    assert result.data == "Hello, workspace!"


@pytest.mark.unit
def test_list_dir_root(fm):
    """List files in the root directory."""
    fm.write_file("a.txt", "a")
    fm.write_file("b.md", "b")
    result = fm.list_dir()
    assert result.success
    names = [e.name for e in result.data]
    assert "a.txt" in names
    assert "b.md" in names


@pytest.mark.unit
def test_list_dir_subdirectory(fm):
    """List files in a subdirectory."""
    fm.write_file("docs/readme.md", "# Docs")
    result = fm.list_dir("docs")
    assert result.success
    names = [e.name for e in result.data]
    assert "readme.md" in names


@pytest.mark.unit
def test_delete_file(fm):
    """Delete a file."""
    fm.write_file("temp.txt", "delete me")
    result = fm.delete_file("temp.txt")
    assert result.success
    # Verify deleted
    result2 = fm.read_file("temp.txt")
    assert not result2.success


@pytest.mark.unit
def test_delete_nonexistent(fm):
    """Deleting a nonexistent file fails gracefully."""
    result = fm.delete_file("nope.txt")
    assert not result.success
    assert "not found" in result.error.lower()


@pytest.mark.unit
def test_mkdir_and_list(fm):
    """Create a directory and list it."""
    fm.mkdir("projects")
    result = fm.list_dir()
    assert result.success
    dirs = [e for e in result.data if e.is_dir]
    assert any(d.name == "projects" for d in dirs)


@pytest.mark.unit
def test_mkdir_nested(fm):
    """Create nested directories."""
    fm.mkdir("a/b/c")
    result = fm.list_dir("a/b")
    assert result.success
    assert any(e.name == "c" for e in result.data)


@pytest.mark.unit
def test_delete_empty_dir(fm):
    """Delete an empty directory."""
    fm.mkdir("empty")
    result = fm.delete_dir("empty")
    assert result.success


@pytest.mark.unit
def test_delete_nonempty_dir(fm):
    """Cannot delete a non-empty directory."""
    fm.write_file("occupied/file.txt", "stuff")
    result = fm.delete_dir("occupied")
    assert not result.success
    assert "not empty" in result.error.lower()


@pytest.mark.unit
def test_delete_root_blocked(fm):
    """Cannot delete the workspace root."""
    result = fm.delete_dir("")
    assert not result.success
    assert result.blocked_reason == "root_protected"


@pytest.mark.unit
def test_move_file(fm):
    """Move/rename a file."""
    fm.write_file("old.txt", "content")
    result = fm.move("old.txt", "new.txt")
    assert result.success
    assert fm.read_file("new.txt").data == "content"
    assert not fm.read_file("old.txt").success


@pytest.mark.unit
def test_move_nonexistent(fm):
    """Moving a nonexistent file fails."""
    result = fm.move("nope.txt", "also_nope.txt")
    assert not result.success


@pytest.mark.unit
def test_workspace_info(fm):
    """Workspace info returns usage stats."""
    fm.write_file("test.txt", "hello")
    info = fm.get_workspace_info()
    assert info["file_count"] == 1
    assert info["total_size_bytes"] > 0
    assert "root" in info


@pytest.mark.unit
def test_read_nonexistent(fm):
    """Reading a nonexistent file fails gracefully."""
    result = fm.read_file("ghost.txt")
    assert not result.success
    assert "not found" in result.error.lower()


@pytest.mark.unit
def test_list_nonexistent_dir(fm):
    """Listing a nonexistent directory fails gracefully."""
    result = fm.list_dir("nonexistent")
    assert not result.success
    assert "not a directory" in result.error.lower()
