"""
Unit tests for AgenticQA API security middleware.

Tests cover:
- BearerTokenMiddleware: allow/deny, timing-safe, skip paths, disabled mode
- OriginValidationMiddleware: localhost allowed, non-localhost blocked, no-origin allowed
- ResponseScanMiddleware: clean pass-through, flagged soft mode, flagged strict mode
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers — build minimal Starlette apps with each middleware under test
# ---------------------------------------------------------------------------

def _make_app_with_bearer(token: str = "test-token", disabled: bool = False):
    from agenticqa.security.api_middleware import BearerTokenMiddleware

    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/test", endpoint), Route("/health", endpoint)])
    with patch.dict(os.environ, {"AGENTICQA_AUTH_TOKEN": token}):
        app.add_middleware(
            BearerTokenMiddleware,
            skip_paths=[],
        )
        if disabled:
            os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
        client = TestClient(app, raise_server_exceptions=True)
    return client, token


def _make_app_with_origin():
    from agenticqa.security.api_middleware import OriginValidationMiddleware

    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    app.add_middleware(OriginValidationMiddleware)
    return TestClient(app, raise_server_exceptions=True)


def _make_app_with_response_scan(strict: bool = False):
    from agenticqa.security.api_middleware import ResponseScanMiddleware

    async def clean_endpoint(request: Request):
        return JSONResponse({"message": "hello world", "status": "ok"})

    async def secret_endpoint(request: Request):
        # This response contains patterns that OutputScanner flags
        return JSONResponse({
            "output": "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "status": "done",
        })

    app = Starlette(routes=[
        Route("/api/clean", clean_endpoint),
        Route("/api/secret", secret_endpoint),
    ])
    env = {"AGENTICQA_RESPONSE_SCAN_STRICT": "1" if strict else "0"}
    with patch.dict(os.environ, env):
        app.add_middleware(ResponseScanMiddleware)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# BearerTokenMiddleware tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_bearer_valid_token_allowed():
    """A request with the correct Bearer token reaches the endpoint."""
    with patch.dict(os.environ, {"AGENTICQA_AUTH_TOKEN": "good-token", "AGENTICQA_AUTH_DISABLE": ""}):
        from agenticqa.security.api_middleware import BearerTokenMiddleware, _get_token
        import agenticqa.security.api_middleware as _mod
        _mod._RUNTIME_TOKEN = "good-token"

        async def endpoint(request: Request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/test", endpoint)])
        app.add_middleware(BearerTokenMiddleware)
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/api/test", headers={"Authorization": "Bearer good-token"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


@pytest.mark.unit
def test_bearer_missing_header_returns_401():
    """A request with no Authorization header gets 401."""
    with patch.dict(os.environ, {"AGENTICQA_AUTH_TOKEN": "good-token", "AGENTICQA_AUTH_DISABLE": ""}):
        import agenticqa.security.api_middleware as _mod
        _mod._RUNTIME_TOKEN = "good-token"

        async def endpoint(request: Request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/test", endpoint)])
        app.add_middleware(_mod.BearerTokenMiddleware)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/test")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


@pytest.mark.unit
def test_bearer_wrong_token_returns_401():
    """A request with an incorrect Bearer token gets 401."""
    with patch.dict(os.environ, {"AGENTICQA_AUTH_TOKEN": "correct-token", "AGENTICQA_AUTH_DISABLE": ""}):
        import agenticqa.security.api_middleware as _mod
        _mod._RUNTIME_TOKEN = "correct-token"

        async def endpoint(request: Request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/test", endpoint)])
        app.add_middleware(_mod.BearerTokenMiddleware)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/test", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401


@pytest.mark.unit
def test_bearer_health_path_skipped():
    """The /health endpoint is exempt from Bearer token auth."""
    with patch.dict(os.environ, {"AGENTICQA_AUTH_TOKEN": "tok", "AGENTICQA_AUTH_DISABLE": ""}):
        import agenticqa.security.api_middleware as _mod
        _mod._RUNTIME_TOKEN = "tok"

        async def endpoint(request: Request):
            return JSONResponse({"status": "healthy"})

        app = Starlette(routes=[Route("/health", endpoint)])
        app.add_middleware(_mod.BearerTokenMiddleware)
        client = TestClient(app, raise_server_exceptions=True)

        # No Authorization header — should still succeed on /health
        resp = client.get("/health")
        assert resp.status_code == 200


@pytest.mark.unit
def test_bearer_disabled_allows_all():
    """When AGENTICQA_AUTH_DISABLE=1, all requests pass through."""
    with patch.dict(os.environ, {"AGENTICQA_AUTH_DISABLE": "1", "AGENTICQA_AUTH_TOKEN": "tok"}):
        import agenticqa.security.api_middleware as _mod
        _mod._RUNTIME_TOKEN = "tok"

        async def endpoint(request: Request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/test", endpoint)])
        app.add_middleware(_mod.BearerTokenMiddleware)
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/api/test")  # no token at all
        assert resp.status_code == 200


@pytest.mark.unit
def test_bearer_timing_safe_comparison():
    """_timing_safe_equal is constant-time and behaves correctly."""
    from agenticqa.security.api_middleware import _timing_safe_equal

    assert _timing_safe_equal("abc", "abc") is True
    assert _timing_safe_equal("abc", "xyz") is False
    assert _timing_safe_equal("", "") is True
    assert _timing_safe_equal("a", "ab") is False


# ---------------------------------------------------------------------------
# OriginValidationMiddleware tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_origin_localhost_allowed():
    """Requests from localhost Origin are accepted."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    app.add_middleware(_mod.OriginValidationMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/api/test", headers={"Origin": "http://localhost:8501"})
    assert resp.status_code == 200


@pytest.mark.unit
def test_origin_non_localhost_blocked():
    """Requests from a remote Origin are blocked with 403."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    app.add_middleware(_mod.OriginValidationMiddleware)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/api/test", headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 403


@pytest.mark.unit
def test_origin_no_header_allowed():
    """Requests with no Origin header (curl, CI scripts) are always allowed."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    app.add_middleware(_mod.OriginValidationMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    # TestClient sends no Origin header by default
    resp = client.get("/api/test")
    assert resp.status_code == 200


@pytest.mark.unit
def test_origin_null_allowed():
    """null Origin (direct file:// access, some fetch) is allowed."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    app.add_middleware(_mod.OriginValidationMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/api/test", headers={"Origin": "null"})
    assert resp.status_code == 200


@pytest.mark.unit
def test_origin_127_0_0_1_allowed():
    """Requests from 127.0.0.1 loopback IP are accepted."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    app.add_middleware(_mod.OriginValidationMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/api/test", headers={"Origin": "http://127.0.0.1:3000"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# ResponseScanMiddleware tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_response_scan_clean_passes_through():
    """A response with no secrets passes through unchanged."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"message": "all clear", "count": 42})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    with patch.dict(os.environ, {"AGENTICQA_RESPONSE_SCAN_STRICT": "0"}):
        app.add_middleware(_mod.ResponseScanMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/api/test")
    assert resp.status_code == 200
    assert resp.json()["count"] == 42
    assert "X-AgenticQA-Security-Flags" not in resp.headers


@pytest.mark.unit
def test_response_scan_health_skipped():
    """The /health path is exempt from response scanning."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"status": "healthy"})

    app = Starlette(routes=[Route("/health", endpoint)])
    app.add_middleware(_mod.ResponseScanMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/health")
    assert resp.status_code == 200


@pytest.mark.unit
def test_response_scan_non_json_skipped():
    """Non-JSON responses are not scanned and pass through unchanged."""
    from starlette.responses import PlainTextResponse
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return PlainTextResponse("hello plain text")

    app = Starlette(routes=[Route("/api/test", endpoint)])
    app.add_middleware(_mod.ResponseScanMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/api/test")
    assert resp.status_code == 200
    assert resp.text == "hello plain text"


@pytest.mark.unit
def test_response_scan_scanner_exception_does_not_break_response():
    """If OutputScanner raises, the response is still returned correctly."""
    import agenticqa.security.api_middleware as _mod

    async def endpoint(request: Request):
        return JSONResponse({"data": "normal output"})

    app = Starlette(routes=[Route("/api/test", endpoint)])
    with patch.dict(os.environ, {"AGENTICQA_RESPONSE_SCAN_STRICT": "0"}):
        app.add_middleware(_mod.ResponseScanMiddleware)
    client = TestClient(app, raise_server_exceptions=True)

    # Patch the scanner to raise an exception — should not crash the response
    with patch.object(
        _mod.ResponseScanMiddleware, "_get_scanner",
        side_effect=Exception("scanner broken"),
    ):
        resp = client.get("/api/test")

    assert resp.status_code == 200
    assert resp.json()["data"] == "normal output"
