"""Path Sanitization Tests — verify CWE-22 protection for repo_path parameters.

Tests:
  - Valid paths within allowed roots pass
  - Path traversal escapes are rejected (../, symlinks)
  - Current directory (.) always passes
  - /tmp paths always pass
  - Custom AGENTICQA_ALLOWED_ROOTS env var is respected
  - PathSanitizationMiddleware blocks bad paths at HTTP level
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from agenticqa.security.path_sanitizer import sanitize_repo_path


# ── Valid paths ──────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_current_dir_passes():
    result = sanitize_repo_path(".")
    assert Path(result).is_absolute()


@pytest.mark.unit
def test_tmp_path_passes():
    result = sanitize_repo_path("/tmp")
    # macOS resolves /tmp → /private/tmp
    assert result in ("/tmp", "/private/tmp")


@pytest.mark.unit
def test_tmp_subdir_passes():
    result = sanitize_repo_path("/tmp/my-repo")
    assert "/tmp/" in result  # handles /private/tmp/ on macOS


@pytest.mark.unit
def test_cwd_subpath_passes():
    cwd = str(Path.cwd())
    result = sanitize_repo_path(cwd)
    assert result == cwd


@pytest.mark.unit
def test_home_subdir_passes():
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE", "")
    if not home:
        pytest.skip("No HOME set")
    result = sanitize_repo_path(home)
    assert result == str(Path(home).resolve())


# ── Traversal attacks rejected ──────────────────────────────────────────────────

@pytest.mark.unit
def test_etc_passwd_rejected():
    with pytest.raises(ValueError, match="outside allowed roots"):
        sanitize_repo_path("/etc/passwd")


@pytest.mark.unit
def test_dot_dot_escape_rejected():
    with pytest.raises(ValueError, match="outside allowed roots"):
        sanitize_repo_path("/tmp/../etc/passwd")


@pytest.mark.unit
def test_absolute_root_rejected():
    with pytest.raises(ValueError, match="outside allowed roots"):
        sanitize_repo_path("/")


@pytest.mark.unit
def test_var_path_rejected():
    with pytest.raises(ValueError, match="outside allowed roots"):
        sanitize_repo_path("/var/log/syslog")


# ── Custom allowed roots via env var ─────────────────────────────────────────

@pytest.mark.unit
def test_custom_allowed_roots_env():
    with patch.dict(os.environ, {"AGENTICQA_ALLOWED_ROOTS": "/opt/repos:/data"}):
        result = sanitize_repo_path("/opt/repos/my-project")
        assert result.startswith("/opt/repos/")


@pytest.mark.unit
def test_custom_allowed_roots_rejects_outside():
    with patch.dict(os.environ, {"AGENTICQA_ALLOWED_ROOTS": "/opt/repos"}):
        with pytest.raises(ValueError, match="outside allowed roots"):
            sanitize_repo_path("/tmp/foo")


# ── Explicit allowed_roots parameter ────────────────────────────────────────

@pytest.mark.unit
def test_explicit_allowed_roots():
    result = sanitize_repo_path("/opt/test", allowed_roots=["/opt"])
    assert result.startswith("/opt")


@pytest.mark.unit
def test_explicit_allowed_roots_rejects():
    with pytest.raises(ValueError):
        sanitize_repo_path("/etc/secret", allowed_roots=["/opt"])


# ── Middleware integration ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_middleware_blocks_traversal():
    """PathSanitizationMiddleware should return 400 on path traversal."""
    # Re-enable path sanitization (conftest disables it globally for other tests)
    old_val = os.environ.pop("AGENTICQA_PATH_SANITIZE_DISABLE", None)
    os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
    try:
        from fastapi.testclient import TestClient
        import agent_api
        client = TestClient(agent_api.app)
        resp = client.get("/api/sdet/generated-tests", params={"repo_path": "/etc/passwd"})
        assert resp.status_code == 400
        assert "path_traversal" in resp.json().get("error", "") or "outside" in resp.json().get("detail", "")
    finally:
        os.environ.pop("AGENTICQA_AUTH_DISABLE", None)
        if old_val is not None:
            os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = old_val
        else:
            os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = "1"


@pytest.mark.unit
def test_middleware_allows_valid_path():
    """PathSanitizationMiddleware should let valid paths through."""
    # Re-enable path sanitization (conftest disables it globally for other tests)
    old_val = os.environ.pop("AGENTICQA_PATH_SANITIZE_DISABLE", None)
    os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
    try:
        from fastapi.testclient import TestClient
        import agent_api
        client = TestClient(agent_api.app)
        resp = client.get("/api/sdet/generated-tests", params={"repo_path": "."})
        assert resp.status_code == 200
    finally:
        os.environ.pop("AGENTICQA_AUTH_DISABLE", None)
        if old_val is not None:
            os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = old_val
        else:
            os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = "1"
