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

import collections
import hmac
import json
import logging
import os
import secrets
import sys
import time
from typing import Callable, Deque, Dict, Sequence

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
        self._prompt_guard = None

    def _get_scanner(self):
        if self._scanner is None:
            try:
                from agenticqa.factory.sandbox.output_scanner import OutputScanner
            except ImportError:
                from src.agenticqa.factory.sandbox.output_scanner import OutputScanner
            self._scanner = OutputScanner()
        return self._scanner

    def _get_prompt_guard(self):
        if self._prompt_guard is None:
            try:
                from agenticqa.security.system_prompt_guard import SystemPromptGuard
            except ImportError:
                from src.agenticqa.security.system_prompt_guard import SystemPromptGuard
            self._prompt_guard = SystemPromptGuard()
        return self._prompt_guard

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

        # System prompt leakage check on the response body text
        try:
            guard = self._get_prompt_guard()
            body_text = body_bytes.decode("utf-8", errors="replace")
            leakage = guard.scan_for_leakage(body_text)
            if leakage:
                critical = [f for f in leakage if f.severity == "critical"]
                logger.warning(
                    "System prompt leakage detected in response (%s): %s",
                    request.url.path,
                    [str(f) for f in leakage[:3]],
                )
                if self._strict and critical:
                    return JSONResponse(
                        status_code=500,
                        content={
                            "detail": "Response blocked: system prompt leakage detected",
                            "findings": [str(f) for f in critical],
                        },
                    )
        except Exception as exc:
            logger.debug("SystemPromptGuard error: %s", exc)

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


# ---------------------------------------------------------------------------
# 4. RateLimitMiddleware — sliding window, no external deps
# ---------------------------------------------------------------------------
#
# Environment variables:
#   AGENTICQA_RATE_LIMIT_RPM   — requests per minute per token (default 60)
#   AGENTICQA_RATE_LIMIT_BURST — burst allowance beyond RPM (default 10)
#
# Heavy endpoints (/api/agents/execute, /api/workflows/run) apply a tighter
# per-endpoint limit of RPM/4 to protect LLM budget.

_HEAVY_PATHS: frozenset[str] = frozenset(
    {"/api/agents/execute", "/api/workflows/run", "/api/agent-factory/from-prompt"}
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token-keyed sliding-window rate limiter.

    Uses a deque of timestamps per token — O(1) amortised with no external deps.
    Falls back to IP address when no Bearer token is present (anonymous clients).
    """

    def __init__(
        self,
        app,
        rpm: int = 0,
        burst: int = 0,
    ) -> None:
        super().__init__(app)
        self._rpm = int(os.getenv("AGENTICQA_RATE_LIMIT_RPM", rpm or 60))
        self._burst = int(os.getenv("AGENTICQA_RATE_LIMIT_BURST", burst or 10))
        self._window_s = 60.0
        # key → deque of hit timestamps
        self._windows: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)

    def _key(self, request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return f"token:{auth[7:32]}"  # truncate to 25 chars — enough to be unique
        return f"ip:{request.client.host if request.client else 'unknown'}"

    def _is_rate_limited(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        dq = self._windows[key]
        cutoff = now - self._window_s
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            return True
        dq.append(now)
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _AUTH_SKIP_PATHS:
            return await call_next(request)
        if os.getenv("AGENTICQA_RATE_LIMIT_DISABLE", "") == "1":
            return await call_next(request)

        key = self._key(request)
        # Heavy endpoints get 1/4 of the normal limit
        limit = self._rpm // 4 if request.url.path in _HEAVY_PATHS else self._rpm + self._burst

        if self._is_rate_limited(key, limit):
            logger.warning("Rate limit exceeded: key=%s path=%s", key[:20], request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Max {self._rpm} requests/minute. Retry after 60s.",
                },
                headers={"Retry-After": "60"},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# 5. InputSizeMiddleware — prevents token-budget exhaustion and JSON bombs
# ---------------------------------------------------------------------------
#
# Environment variables:
#   AGENTICQA_MAX_BODY_BYTES  — max request body size in bytes (default 512 KB)
#   AGENTICQA_MAX_JSON_DEPTH  — max JSON nesting depth (default 20)

_DEFAULT_MAX_BYTES = 512 * 1024  # 512 KB
_DEFAULT_MAX_DEPTH = 20


def _json_depth(obj, current: int = 0) -> int:
    if current > _DEFAULT_MAX_DEPTH:
        return current
    if isinstance(obj, dict):
        return max((_json_depth(v, current + 1) for v in obj.values()), default=current)
    if isinstance(obj, list):
        return max((_json_depth(v, current + 1) for v in obj), default=current)
    return current


class InputSizeMiddleware(BaseHTTPMiddleware):
    """
    Rejects requests that exceed body-size or JSON-depth limits.

    Prevents:
    - Context-window overflow attacks (enormous prompts evict system instructions)
    - JSON/YAML bomb denial-of-service via deeply-nested structures
    """

    def __init__(self, app, max_bytes: int = 0, max_depth: int = 0) -> None:
        super().__init__(app)
        self._max_bytes = int(os.getenv("AGENTICQA_MAX_BODY_BYTES", max_bytes or _DEFAULT_MAX_BYTES))
        self._max_depth = int(os.getenv("AGENTICQA_MAX_JSON_DEPTH", max_depth or _DEFAULT_MAX_DEPTH))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)
        if request.url.path in _AUTH_SKIP_PATHS:
            return await call_next(request)

        body = await request.body()

        if len(body) > self._max_bytes:
            logger.warning(
                "Request body too large: %d bytes > %d limit (path=%s)",
                len(body), self._max_bytes, request.url.path,
            )
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request body too large",
                    "detail": f"Max {self._max_bytes // 1024} KB allowed",
                },
            )

        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type and body:
            try:
                parsed = json.loads(body)
                depth = _json_depth(parsed)
                if depth > self._max_depth:
                    logger.warning(
                        "JSON nesting too deep: depth=%d > %d (path=%s)",
                        depth, self._max_depth, request.url.path,
                    )
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "JSON nesting depth exceeded",
                            "detail": f"Max depth {self._max_depth} allowed",
                        },
                    )
            except json.JSONDecodeError:
                pass  # let FastAPI return its own 422

        # Token budget / sponge-attack check on text fields
        if body and not os.getenv("AGENTICQA_RATE_LIMIT_DISABLE"):
            try:
                from agenticqa.security.token_budget_guard import TokenBudgetGuard
                _raw = body.decode("utf-8", errors="replace")
                _result = TokenBudgetGuard().check_input(_raw)
                if not _result.safe:
                    logger.warning(
                        "Token budget guard: risk=%.2f signals=%s (path=%s)",
                        _result.risk_score, _result.signals, request.url.path,
                    )
                    if _result.risk_score >= 0.8:
                        return JSONResponse(
                            status_code=400,
                            content={
                                "error": "Request flagged as token amplification attack",
                                "detail": f"Risk score {_result.risk_score:.2f}: {_result.signals}",
                            },
                        )
            except Exception:
                pass  # non-blocking

        # Re-attach body so downstream handlers can read it
        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive
        return await call_next(request)
