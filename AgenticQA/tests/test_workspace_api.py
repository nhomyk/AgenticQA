"""Tests for workspace API endpoints.

Validates:
  - File CRUD endpoints
  - Mail endpoints (config-dependent graceful failures)
  - Link endpoints (bookmarks, SSRF blocking)
  - Safety status endpoint
"""
import os
import pytest


@pytest.fixture
def client():
    """FastAPI TestClient with auth disabled."""
    os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
    os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = "1"
    from fastapi.testclient import TestClient
    import agent_api
    return TestClient(agent_api.app)


# ── File endpoints ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_workspace_list_files(client):
    """GET /api/workspace/files returns a listing."""
    resp = client.get("/api/workspace/files")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "entries" in data


@pytest.mark.unit
def test_workspace_write_and_read(client):
    """Write a file then read it back via API."""
    # Write
    wr = client.post("/api/workspace/files/write",
                     json={"path": "test_api.txt", "content": "Hello API"})
    assert wr.status_code == 200

    # Read
    rd = client.get("/api/workspace/files/read", params={"path": "test_api.txt"})
    assert rd.status_code == 200
    assert rd.json()["content"] == "Hello API"

    # Cleanup
    client.delete("/api/workspace/files", params={"path": "test_api.txt"})


@pytest.mark.unit
def test_workspace_write_blocked_extension(client):
    """Writing a blocked extension returns 403."""
    resp = client.post("/api/workspace/files/write",
                       json={"path": "evil.exe", "content": "MZ"})
    assert resp.status_code == 403


@pytest.mark.unit
def test_workspace_mkdir(client):
    """POST /api/workspace/files/mkdir creates a directory."""
    resp = client.post("/api/workspace/files/mkdir",
                       json={"path": "test_dir_api"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.unit
def test_workspace_info(client):
    """GET /api/workspace/files/info returns workspace stats."""
    resp = client.get("/api/workspace/files/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "file_count" in data
    assert "total_size_bytes" in data


@pytest.mark.unit
def test_workspace_write_missing_path(client):
    """Write without path returns 400."""
    resp = client.post("/api/workspace/files/write",
                       json={"content": "no path"})
    assert resp.status_code == 400


# ── Link endpoints ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_workspace_fetch_ssrf_blocked(client):
    """Fetching a private IP is blocked (SSRF prevention)."""
    resp = client.post("/api/workspace/links/fetch",
                       json={"url": "http://169.254.169.254/latest/meta-data/"})
    assert resp.status_code == 403


@pytest.mark.unit
def test_workspace_add_and_list_bookmarks(client):
    """Add a bookmark and list it back."""
    # Add
    resp = client.post("/api/workspace/links/bookmarks",
                       json={"url": "https://example.com", "title": "Ex"})
    assert resp.status_code == 200
    bm_id = resp.json().get("bookmark_id")

    # List
    list_resp = client.get("/api/workspace/links/bookmarks")
    assert list_resp.status_code == 200
    bookmarks = list_resp.json().get("bookmarks", [])
    assert any(b["url"] == "https://example.com" for b in bookmarks)

    # Cleanup
    if bm_id:
        client.delete("/api/workspace/links/bookmarks",
                      params={"bookmark_id": bm_id})


@pytest.mark.unit
def test_workspace_add_bookmark_invalid_url(client):
    """Adding a bookmark with private IP is blocked."""
    resp = client.post("/api/workspace/links/bookmarks",
                       json={"url": "http://localhost/admin"})
    assert resp.status_code == 400


# ── Safety status endpoint ───────────────────────────────────────────────────


@pytest.mark.unit
def test_workspace_safety_status(client):
    """GET /api/workspace/safety/status returns gate status."""
    resp = client.get("/api/workspace/safety/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "lease" in data
    assert "pending_approvals" in data


# ── Mail endpoints (unconfigured) ────────────────────────────────────────────


@pytest.mark.unit
def test_workspace_mail_folders_unconfigured(client):
    """Mail folders fails gracefully when not configured."""
    resp = client.get("/api/workspace/mail/folders")
    assert resp.status_code == 400
    assert "not configured" in resp.json().get("detail", "").lower()


@pytest.mark.unit
def test_workspace_mail_messages_unconfigured(client):
    """Mail messages fails gracefully when not configured."""
    resp = client.get("/api/workspace/mail/messages")
    assert resp.status_code == 400


@pytest.mark.unit
def test_workspace_mail_send_missing_fields(client):
    """Send without required fields returns 400."""
    resp = client.post("/api/workspace/mail/send", json={"body": "test"})
    assert resp.status_code == 400
