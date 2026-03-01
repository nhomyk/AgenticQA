"""Tests for the safe link tools.

Validates:
  - URL validation (SSRF prevention, scheme enforcement)
  - Bookmark CRUD operations
  - Bookmark persistence
"""
import json
import pytest
from pathlib import Path

from agenticqa.workspace.link_tools import (
    SafeLinkManager,
    Bookmark,
    FetchResult,
    LinkOpResult,
    validate_url,
)


# ── URL validation (SSRF prevention) ─────────────────────────────────────────


@pytest.mark.unit
def test_validate_url_valid_https():
    """Valid HTTPS URL passes."""
    assert validate_url("https://example.com") is None


@pytest.mark.unit
def test_validate_url_valid_http():
    """Valid HTTP URL passes."""
    assert validate_url("http://example.com") is None


@pytest.mark.unit
def test_validate_url_blocks_ftp():
    """FTP scheme is blocked."""
    err = validate_url("ftp://evil.com/file")
    assert err is not None
    assert "not allowed" in err


@pytest.mark.unit
def test_validate_url_blocks_javascript():
    """javascript: scheme is blocked."""
    err = validate_url("javascript:alert(1)")
    assert err is not None


@pytest.mark.unit
def test_validate_url_blocks_localhost():
    """localhost is blocked (SSRF)."""
    err = validate_url("http://localhost/admin")
    assert err is not None
    assert "SSRF" in err


@pytest.mark.unit
def test_validate_url_blocks_127():
    """127.0.0.1 is blocked (SSRF)."""
    err = validate_url("http://127.0.0.1:9200/_cluster/health")
    assert err is not None
    assert "SSRF" in err


@pytest.mark.unit
def test_validate_url_blocks_10_network():
    """10.x.x.x is blocked (SSRF)."""
    err = validate_url("http://10.0.0.1/secret")
    assert err is not None


@pytest.mark.unit
def test_validate_url_blocks_172_16():
    """172.16.x.x is blocked (SSRF)."""
    err = validate_url("http://172.16.0.1/secret")
    assert err is not None


@pytest.mark.unit
def test_validate_url_blocks_192_168():
    """192.168.x.x is blocked (SSRF)."""
    err = validate_url("http://192.168.1.1/admin")
    assert err is not None


@pytest.mark.unit
def test_validate_url_blocks_metadata():
    """Cloud metadata endpoint is blocked (SSRF)."""
    err = validate_url("http://metadata.google.internal/computeMetadata/v1/")
    assert err is not None
    assert "SSRF" in err


@pytest.mark.unit
def test_validate_url_blocks_ipv6_loopback():
    """IPv6 loopback ::1 is blocked (SSRF)."""
    err = validate_url("http://[::1]/")
    assert err is not None


@pytest.mark.unit
def test_validate_url_blocks_link_local():
    """169.254.x.x (link-local) is blocked (SSRF)."""
    err = validate_url("http://169.254.169.254/latest/meta-data/")
    assert err is not None


@pytest.mark.unit
def test_validate_url_blocks_no_host():
    """URL without host is blocked."""
    err = validate_url("https://")
    assert err is not None


# ── Bookmark CRUD ────────────────────────────────────────────────────────────


@pytest.fixture
def link_mgr(tmp_path):
    """Link manager with temporary bookmark storage."""
    return SafeLinkManager(bookmarks_path=tmp_path / "bookmarks.json")


@pytest.mark.unit
def test_add_bookmark(link_mgr):
    """Add a bookmark."""
    result = link_mgr.add_bookmark("https://example.com", title="Example")
    assert result.success
    assert "bookmark_id" in result.data


@pytest.mark.unit
def test_add_bookmark_invalid_url(link_mgr):
    """Adding a bookmark with invalid URL fails."""
    result = link_mgr.add_bookmark("ftp://evil.com")
    assert not result.success
    assert result.blocked_reason == "url_validation"


@pytest.mark.unit
def test_list_bookmarks_empty(link_mgr):
    """List bookmarks when none exist."""
    result = link_mgr.list_bookmarks()
    assert result.success
    assert result.data == []


@pytest.mark.unit
def test_list_bookmarks_after_add(link_mgr):
    """List bookmarks after adding one."""
    link_mgr.add_bookmark("https://example.com", title="Example", tags=["test"])
    result = link_mgr.list_bookmarks()
    assert result.success
    assert len(result.data) == 1
    assert result.data[0]["title"] == "Example"


@pytest.mark.unit
def test_list_bookmarks_filter_by_tag(link_mgr):
    """Filter bookmarks by tag."""
    link_mgr.add_bookmark("https://a.com", tags=["dev"])
    link_mgr.add_bookmark("https://b.com", tags=["docs"])
    result = link_mgr.list_bookmarks(tag="dev")
    assert result.success
    assert len(result.data) == 1
    assert result.data[0]["url"] == "https://a.com"


@pytest.mark.unit
def test_delete_bookmark(link_mgr):
    """Delete a bookmark by ID."""
    add_result = link_mgr.add_bookmark("https://example.com")
    bm_id = add_result.data["bookmark_id"]
    del_result = link_mgr.delete_bookmark(bm_id)
    assert del_result.success
    assert len(link_mgr.list_bookmarks().data) == 0


@pytest.mark.unit
def test_delete_bookmark_nonexistent(link_mgr):
    """Deleting a nonexistent bookmark fails gracefully."""
    result = link_mgr.delete_bookmark("nonexistent_id")
    assert not result.success
    assert "not found" in result.error.lower()


# ── Bookmark persistence ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_bookmarks_persist(tmp_path):
    """Bookmarks are saved to disk and reloaded."""
    bm_path = tmp_path / "bookmarks.json"

    mgr1 = SafeLinkManager(bookmarks_path=bm_path)
    mgr1.add_bookmark("https://persist.com", title="Persist")

    # Reload from disk
    mgr2 = SafeLinkManager(bookmarks_path=bm_path)
    result = mgr2.list_bookmarks()
    assert result.success
    assert len(result.data) == 1
    assert result.data[0]["url"] == "https://persist.com"


@pytest.mark.unit
def test_bookmarks_file_format(tmp_path):
    """Bookmarks file has expected JSON structure."""
    bm_path = tmp_path / "bookmarks.json"
    mgr = SafeLinkManager(bookmarks_path=bm_path)
    mgr.add_bookmark("https://example.com", title="Ex", tags=["test"])

    data = json.loads(bm_path.read_text())
    assert "bookmarks" in data
    assert len(data["bookmarks"]) == 1
    bm = data["bookmarks"][0]
    assert bm["url"] == "https://example.com"
    assert bm["title"] == "Ex"
    assert bm["tags"] == ["test"]
    assert "bookmark_id" in bm
    assert "added_at" in bm


# ── Bookmark dataclass ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_bookmark_auto_id():
    """Bookmark generates an ID from URL hash."""
    bm = Bookmark(url="https://example.com")
    assert bm.bookmark_id
    assert len(bm.bookmark_id) == 12


@pytest.mark.unit
def test_bookmark_auto_timestamp():
    """Bookmark sets added_at automatically."""
    bm = Bookmark(url="https://example.com")
    assert bm.added_at > 0


# ── FetchResult / LinkOpResult ───────────────────────────────────────────────


@pytest.mark.unit
def test_fetch_result_success():
    """FetchResult success case."""
    r = FetchResult(success=True, url="https://example.com", status_code=200,
                    text="Hello")
    assert r.success
    assert r.text == "Hello"
    assert r.scan_flags == []


@pytest.mark.unit
def test_fetch_result_blocked():
    """FetchResult blocked case."""
    r = FetchResult(success=False, url="http://localhost", error="SSRF",
                    blocked_reason="url_validation")
    assert not r.success
    assert r.blocked_reason == "url_validation"


@pytest.mark.unit
def test_link_op_result():
    """LinkOpResult structure."""
    r = LinkOpResult(success=True, action="add_bookmark",
                     data={"bookmark_id": "abc"})
    assert r.success
    assert r.action == "add_bookmark"


# ── Fetch URL (with mocked requests) ────────────────────────────────────────


@pytest.mark.unit
def test_fetch_url_ssrf_blocked(link_mgr):
    """fetch_url blocks SSRF attempts."""
    result = link_mgr.fetch_url("http://169.254.169.254/latest/meta-data/")
    assert not result.success
    assert result.blocked_reason == "url_validation"


@pytest.mark.unit
def test_fetch_url_invalid_scheme(link_mgr):
    """fetch_url blocks non-http schemes."""
    result = link_mgr.fetch_url("file:///etc/passwd")
    assert not result.success
    assert result.blocked_reason == "url_validation"
