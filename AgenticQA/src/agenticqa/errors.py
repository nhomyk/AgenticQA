"""Standardized error responses for the AgenticQA API.

Every error response follows the shape::

    {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Human-readable description",
            "request_id": "abc123-...",
            "details": {}        # optional, extra context
        }
    }

Usage in agent_api.py::

    from agenticqa.errors import install_error_handlers
    install_error_handlers(app)

"""
from __future__ import annotations

import logging
import traceback
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def _error_body(
    code: str,
    message: str,
    request_id: str,
    status: int,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "status": status,
        },
        # Backwards-compatible: existing code checks resp.json()["detail"]
        "detail": message,
    }
    if details:
        body["error"]["details"] = details
    return body


def _request_id(request: Request) -> str:
    """Extract or generate a request ID."""
    return request.headers.get("X-Request-ID", str(uuid.uuid4())[:12])


def install_error_handlers(app: FastAPI) -> None:
    """Install global exception handlers that produce standardized errors."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        rid = _request_id(request)
        code = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
        }.get(exc.status_code, f"HTTP_{exc.status_code}")

        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, str(exc.detail), rid, exc.status_code),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        rid = _request_id(request)
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            errors.append({"field": loc, "message": err.get("msg", "")})

        return JSONResponse(
            status_code=422,
            content=_error_body(
                "VALIDATION_ERROR",
                "Request validation failed",
                rid,
                422,
                details={"errors": errors},
            ),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = _request_id(request)
        logger.error(
            "Unhandled exception [%s] %s: %s\n%s",
            rid,
            type(exc).__name__,
            exc,
            traceback.format_exc()[-500:],
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "INTERNAL_ERROR",
                "An internal error occurred. Reference ID: " + rid,
                rid,
                500,
            ),
            headers={"X-Request-ID": rid},
        )
