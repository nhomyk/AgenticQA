"""
Webhook Notification System

Posts a JSON summary to a configurable URL when a pipeline run completes.
The URL is read from the AGENTICQA_WEBHOOK_URL environment variable.

Payload schema
--------------
{
    "event": "pipeline_complete",
    "timestamp": "<ISO-8601>",
    "release_readiness_score": 72.5,
    "recommendation": "SHIP IT",
    "tests_passed": 18,
    "tests_total": 20,
    "owasp_critical_count": 0,
    "feature_description": "Add OAuth2 login"
}

Retry logic
-----------
Default: 3 retries with exponential backoff (1s, 2s, 4s).
Raises WebhookDeliveryError after all retries are exhausted.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


class WebhookDeliveryError(Exception):
    """Raised when all retry attempts fail."""


@dataclass
class WebhookPayload:
    release_readiness_score: float
    recommendation: str          # "SHIP IT" or "DO NOT SHIP"
    tests_passed: int
    tests_total: int
    owasp_critical_count: int
    feature_description: str
    timestamp: str = ""          # auto-set if empty

    def to_dict(self) -> dict:
        ts = self.timestamp or datetime.now(tz=timezone.utc).isoformat()
        return {
            "event": "pipeline_complete",
            "timestamp": ts,
            "release_readiness_score": self.release_readiness_score,
            "recommendation": self.recommendation,
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "owasp_critical_count": self.owasp_critical_count,
            "feature_description": self.feature_description,
        }


class WebhookNotifier:
    """Sends pipeline results to a user-configured webhook URL."""

    def __init__(
        self,
        url: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 10,
    ) -> None:
        self.url = url or os.environ.get("AGENTICQA_WEBHOOK_URL", "")
        self.max_retries = max_retries
        self.timeout = timeout

    def notify(self, payload: WebhookPayload) -> dict:
        """
        POST the payload to the configured URL.

        Returns the parsed JSON response body on success.
        Raises WebhookDeliveryError if all retries fail.
        Raises ValueError if AGENTICQA_WEBHOOK_URL is not set.
        """
        if not self.url:
            raise ValueError(
                "Webhook URL not configured. "
                "Set AGENTICQA_WEBHOOK_URL environment variable."
            )

        body = json.dumps(payload.to_dict()).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AgenticQA-Webhook/1.0",
        }

        last_error: Exception = RuntimeError("no attempts made")
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                wait = 2 ** (attempt - 1)          # 1s, 2s, 4s, …
                time.sleep(wait)

            try:
                req = urllib.request.Request(
                    self.url, data=body, headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return {"raw": raw.decode("utf-8", errors="replace")}

            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
                last_error = exc
                continue

        raise WebhookDeliveryError(
            f"Webhook delivery failed after {self.max_retries + 1} attempt(s). "
            f"Last error: {last_error}"
        ) from last_error
