"""
AgenticQA API Security Middleware

Three Starlette/FastAPI middlewares modelled after docker/mcp-gateway defensive patterns:

1. BearerTokenMiddleware  — timing-safe Bearer token auth (hmac.compare_digest)
2. OriginValidationMiddleware — localhost-only Origin header check (DNS rebinding defence)
3. ResponseScanMiddleware  — OutputScanner on JSON responses (credential leak prevention)

Environment variables
---------------------
AGENTICQA_AUTH_TOKEN   — static token; auto-generated and printed to stderr if absent
AGENTICQA_AUTH_DISABLE — set to "1" to skip auth (local dev without env setup)
AGENTICQA_RESPONSE_SCAN_STRICT — set to "1" to block responses that contain secrets
                                  (default: log-only / add warning header)
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import sys
from typing import Callable, Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public endpoints that skip Bearer token checks
# ---------------------------------------------------------------------------
_AUTH_SKIP_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)

# Localhost origins the dashboard / local frontends send
_ALLOWED_ORIGINS: frozenset[str] = frozenset(
    {
        "http://localhost",
        "http://localhost:8501",  # Streamlit dashboard
        "http://localhost:3000",  # Dev React / Next.js
        "http://localhost:8000",  # uvicorn self
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        # Allow null origin (curl / direct fetch from local file)
        "null",
    }
)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _load_or_generate_token() -> str:
    """
    Return the Bearer token from AGENTICQA_AUTH_TOKEN env var.
    If the env var is not set, generate a random token and print it to stderr
    (matching docker/mcp-gateway's UX pattern: auto-generated, logged once).
    """
    token = os.environ.get("AGENTICQA_AUTH_TOKEN", "").strip()
    if token:
        return token

    token = secrets.token_urlsafe(32)
    # Print exactly once at startup — operators copy this into their client
    print(
        f"\n[AgenticQA] No AGENTICQA_AUTH_TOKEN set. Auto-generated for this session:\n"
        f"  Bearer token: {token}\n"
        f"  Set AGENTICQA_AUTH_TOKEN={token} to persist across restarts.\n",
        file=sys.stderr,
    )
    os.environ["AGENTICQA_AUTH_TOKEN"] = token  # Share with other middleware/tests
    return token


_RUNTIME_TOKEN: str = ""  # lazily initialised on first middleware call


def _get_token() -> str:
    global _RUNTIME_TOKEN
    if not _RUNTIME_TOKEN:
        _RUNTIME_TOKEN = _load_or_generate_token()
    return _RUNTIME_TOKEN


def _timing_safe_equal(a: str, b: str) -> bool:
    """constant-time string comparison (hmac.compare_digest on bytes)."""
    return hmac.compare_digest(a.encode(), b.encode())


# ---------------------------------------------------------------------------
# 1. Bearer Token Middleware
# ---------------------------------------------------------------------------

class BearerTokenMiddleware(BaseHTTPMiddleware):
    """
    Require a valid Bearer token on every request except public endpoints.

    Mirrors docker/mcp-gateway's authenticationMiddleware:
    - Skips configured public paths
    - Uses hmac.compare_digest to prevent timing-oracle attacks
    - Returns 401 with WWW-Authenticate challenge on failure
    """

    def __init__(self, app, skip_paths: Sequence[str] = ()) -> None:
        super().__init__(app)
        self._skip = frozenset(skip_paths) | _AUTH_SKIP_PATHS
        self._disabled = os.environ.get("AGENTICQA_AUTH_DISABLE", "").strip() == "1"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._disabled:
            return await call_next(request)

        if request.url.path in self._skip:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or malformed Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        provided = auth_header[len("Bearer "):]
        expected = _get_token()

        if not _timing_safe_equal(provided, expected):
            logger.warning(
                "Bearer token mismatch from %s %s",
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# 2. Origin Validation Middleware (DNS rebinding defence)
# ---------------------------------------------------------------------------

class OriginValidationMiddleware(BaseHTTPMiddleware):
    """
    Block requests from non-localhost Origins.

    Web browsers send an Origin header on cross-origin requests. If an
    attacker tricks a user's browser into visiting a malicious page, that page
    can make authenticated requests to localhost APIs using the user's session.
    Rejecting non-localhost Origins prevents this attack class.

    Requests with *no* Origin header (direct API clients, curl, CI scripts)
    are always permitted — this is consistent with browser security model where
    only browsers send Origin.

    Mirrors docker/mcp-gateway's originSecurityHandler / isAllowedOrigin().
    """

    def __init__(self, app, extra_origins: Sequence[str] = ()) -> None:
        super().__init__(app)
        self._allowed = _ALLOWED_ORIGINS | frozenset(extra_origins)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        origin = request.headers.get("Origin", "")

        if origin and origin not in self._allowed:
            logger.warning(
                "Blocked request from disallowed Origin=%r path=%s",
                origin,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Origin not allowed. AgenticQA API only accepts requests "
                        "from localhost. Set AGENTICQA_AUTH_DISABLE=1 for remote "
                        "access (use with caution)."
                    )
                },
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# 3. Response Secret Scanning Middleware
# ---------------------------------------------------------------------------

class ResponseScanMiddleware(BaseHTTPMiddleware):
    """
    Scan JSON API responses for accidental credential/secret leaks.

    Uses AgenticQA's own OutputScanner (the same scanner that catches secrets
    in agent outputs) on every JSON response body.

    Modes:
    - Soft (default): add X-AgenticQA-Security-Flags header, log warning
    - Strict (AGENTICQA_RESPONSE_SCAN_STRICT=1): return 500 and block the
      response, preventing the credential from reaching the caller.

    Mirrors docker/mcp-gateway's BlockSecretsMiddleware.
    """

    # Paths whose responses we don't bother scanning (large binary / health)
    _SKIP_SCAN_PATHS: frozenset[str] = frozenset(
        {"/health", "/docs", "/openapi.json", "/redoc"}
    )

    def __init__(self, app) -> None:
        super().__init__(app)
        self._strict = (
            os.environ.get("AGENTICQA_RESPONSE_SCAN_STRICT", "").strip() == "1"
        )
        self._scanner = None  # lazy import to avoid circular deps at module load

    def _get_scanner(self):
        if self._scanner is None:
            try:
                from agenticqa.factory.sandbox.output_scanner import OutputScanner
            except ImportError:
                from src.agenticqa.factory.sandbox.output_scanner import OutputScanner
            self._scanner = OutputScanner()
        return self._scanner

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if request.url.path in self._SKIP_SCAN_PATHS:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Consume and buffer the response body
        body_chunks = []
        async for chunk in response.body_iterator:
            body_chunks.append(chunk)
        body_bytes = b"".join(body_chunks)

        try:
            body_obj = json.loads(body_bytes)
        except Exception:
            # Not valid JSON — pass through unchanged
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type,
            )

        try:
            scanner = self._get_scanner()
            scan_result = scanner.scan(body_obj)
        except Exception as exc:
            logger.debug("ResponseScanMiddleware scanner error: %s", exc)
            scan_result = {"clean": True, "flags": []}

        if not scan_result.get("clean", True):
            flags = scan_result.get("flags", [])
            labels = [f.get("label", "?") for f in flags]
            logger.warning(
                "Response secret scan: %d flag(s) on %s — %s",
                len(flags),
                request.url.path,
                labels,
            )

            if self._strict:
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": (
                            "Response blocked: potential credential detected in output. "
                            "Set AGENTICQA_RESPONSE_SCAN_STRICT=0 to switch to log-only mode."
                        ),
                        "flags": labels,
                    },
                )

            # Soft mode: pass through but annotate
            headers = dict(response.headers)
            headers["X-AgenticQA-Security-Flags"] = ", ".join(labels[:5])  # cap header size
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=headers,
                media_type=content_type,
            )

        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=content_type,
        )
