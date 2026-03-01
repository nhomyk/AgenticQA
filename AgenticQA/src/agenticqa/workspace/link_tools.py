"""Safe link/URL tools for the AgenticQA workspace.

URLs are fetched server-side and content is scanned by OutputScanner
before being presented to the user or agents.  Bookmarks are stored
in a sandboxed JSON file.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_BOOKMARKS_PATH = Path.home() / ".agenticqa" / "workspace" / "bookmarks.json"
MAX_FETCH_SIZE = 5 * 1024 * 1024  # 5 MB
FETCH_TIMEOUT = 15  # seconds

# Schemes allowed for fetching
ALLOWED_SCHEMES = frozenset({"http", "https"})

# Block private/internal IPs (SSRF prevention)
_PRIVATE_HOST_PATTERNS = [
    re.compile(r"^localhost$", re.I),
    re.compile(r"^127\."),
    re.compile(r"^10\."),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^0\.0\.0\.0$"),
    re.compile(r"^\[?::1\]?$"),
    re.compile(r"^169\.254\."),  # link-local
    re.compile(r"^metadata\.google\.internal$", re.I),
]


# ── Data types ───────────────────────────────────────────────────────────────


@dataclass
class Bookmark:
    """A saved URL with metadata."""
    url: str
    title: str = ""
    tags: List[str] = field(default_factory=list)
    added_at: float = 0.0
    bookmark_id: str = ""

    def __post_init__(self) -> None:
        if not self.added_at:
            self.added_at = time.time()
        if not self.bookmark_id:
            self.bookmark_id = hashlib.sha256(
                self.url.encode()
            ).hexdigest()[:12]


@dataclass
class FetchResult:
    """Result of fetching a URL."""
    success: bool
    url: str
    status_code: int = 0
    content_type: str = ""
    text: str = ""
    error: Optional[str] = None
    blocked_reason: Optional[str] = None
    scan_flags: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class LinkOpResult:
    """Result of a link operation."""
    success: bool
    action: str  # fetch, add_bookmark, list_bookmarks, delete_bookmark
    error: Optional[str] = None
    data: Any = None
    blocked_reason: Optional[str] = None


# ── URL validation ───────────────────────────────────────────────────────────


def validate_url(url: str) -> Optional[str]:
    """Return an error string if *url* is unsafe, else None."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL"

    if parsed.scheme not in ALLOWED_SCHEMES:
        return f"Scheme '{parsed.scheme}' not allowed (use http/https)"

    host = parsed.hostname or ""
    if not host:
        return "No host in URL"

    for pattern in _PRIVATE_HOST_PATTERNS:
        if pattern.match(host):
            return f"Blocked: private/internal host '{host}' (SSRF prevention)"

    return None


# ── Safe link manager ────────────────────────────────────────────────────────


class SafeLinkManager:
    """URL fetch + bookmark management with safety gates."""

    def __init__(self, bookmarks_path: Optional[Path] = None) -> None:
        self.bookmarks_path = bookmarks_path or DEFAULT_BOOKMARKS_PATH
        self._bookmarks: Dict[str, Bookmark] = {}
        self._load_bookmarks()

    # ── bookmarks persistence ─────────────────────────────────────────────

    def _load_bookmarks(self) -> None:
        if self.bookmarks_path.exists():
            try:
                data = json.loads(self.bookmarks_path.read_text("utf-8"))
                for entry in data.get("bookmarks", []):
                    bm = Bookmark(**entry)
                    self._bookmarks[bm.bookmark_id] = bm
            except Exception:
                self._bookmarks = {}

    def _save_bookmarks(self) -> None:
        self.bookmarks_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "bookmarks": [
                {
                    "url": bm.url,
                    "title": bm.title,
                    "tags": bm.tags,
                    "added_at": bm.added_at,
                    "bookmark_id": bm.bookmark_id,
                }
                for bm in self._bookmarks.values()
            ]
        }
        self.bookmarks_path.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ── URL fetch ─────────────────────────────────────────────────────────

    def fetch_url(self, url: str) -> FetchResult:
        """Fetch *url* with safety checks. Returns text content."""
        error = validate_url(url)
        if error:
            return FetchResult(success=False, url=url, error=error,
                               blocked_reason="url_validation")

        try:
            import requests as _requests
        except ImportError:
            return FetchResult(success=False, url=url,
                               error="requests library not installed")

        try:
            resp = _requests.get(
                url,
                timeout=FETCH_TIMEOUT,
                headers={"User-Agent": "AgenticQA-Workspace/1.0"},
                stream=True,
                allow_redirects=True,
            )

            # Check redirect target for SSRF
            if resp.url != url:
                redir_error = validate_url(resp.url)
                if redir_error:
                    return FetchResult(
                        success=False, url=url,
                        error=f"Redirect blocked: {redir_error}",
                        blocked_reason="ssrf_redirect",
                    )

            # Size guard
            content_length = resp.headers.get("Content-Length", "")
            if content_length and int(content_length) > MAX_FETCH_SIZE:
                return FetchResult(
                    success=False, url=url,
                    error=f"Response too large ({content_length} bytes)",
                    blocked_reason="size_limit",
                )

            # Read with size limit
            chunks: List[bytes] = []
            total = 0
            for chunk in resp.iter_content(8192):
                total += len(chunk)
                if total > MAX_FETCH_SIZE:
                    return FetchResult(
                        success=False, url=url,
                        error="Response exceeded size limit during download",
                        blocked_reason="size_limit",
                    )
                chunks.append(chunk)

            raw_bytes = b"".join(chunks)
            text = raw_bytes.decode("utf-8", errors="replace")

            # Output scan (post-fetch)
            scan_flags: List[Dict[str, str]] = []
            try:
                from agenticqa.factory.sandbox.output_scanner import OutputScanner
                scanner = OutputScanner()
                report = scanner.scan({"url": url, "content": text[:10000]})
                if not report.get("clean", True):
                    scan_flags = report.get("flags", [])
            except Exception:
                pass  # scanner unavailable — allow content through

            return FetchResult(
                success=True,
                url=resp.url,
                status_code=resp.status_code,
                content_type=resp.headers.get("Content-Type", ""),
                text=text,
                scan_flags=scan_flags,
            )

        except Exception as exc:
            return FetchResult(success=False, url=url, error=str(exc))

    # ── bookmark operations ───────────────────────────────────────────────

    def add_bookmark(self, url: str, title: str = "",
                     tags: Optional[List[str]] = None) -> LinkOpResult:
        """Save a URL as a bookmark."""
        error = validate_url(url)
        if error:
            return LinkOpResult(success=False, action="add_bookmark",
                                error=error, blocked_reason="url_validation")

        bm = Bookmark(url=url, title=title or url, tags=tags or [])
        self._bookmarks[bm.bookmark_id] = bm
        self._save_bookmarks()

        return LinkOpResult(success=True, action="add_bookmark",
                            data={"bookmark_id": bm.bookmark_id, "url": url})

    def list_bookmarks(self, tag: Optional[str] = None) -> LinkOpResult:
        """List all bookmarks, optionally filtered by tag."""
        bms = list(self._bookmarks.values())
        if tag:
            bms = [b for b in bms if tag in b.tags]

        data = [
            {
                "bookmark_id": b.bookmark_id,
                "url": b.url,
                "title": b.title,
                "tags": b.tags,
                "added_at": b.added_at,
            }
            for b in sorted(bms, key=lambda x: x.added_at, reverse=True)
        ]
        return LinkOpResult(success=True, action="list_bookmarks", data=data)

    def delete_bookmark(self, bookmark_id: str) -> LinkOpResult:
        """Remove a bookmark by ID."""
        if bookmark_id not in self._bookmarks:
            return LinkOpResult(success=False, action="delete_bookmark",
                                error="Bookmark not found")

        del self._bookmarks[bookmark_id]
        self._save_bookmarks()
        return LinkOpResult(success=True, action="delete_bookmark")
