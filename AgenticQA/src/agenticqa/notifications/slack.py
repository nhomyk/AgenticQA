"""Slack notification integration for AgenticQA.

Sends scan results, trend alerts, and compliance updates to Slack
via incoming webhooks using Block Kit formatting.

Setup:
    1. Create a Slack Incoming Webhook: https://api.slack.com/messaging/webhooks
    2. Set AGENTICQA_SLACK_WEBHOOK_URL environment variable
    3. AgenticQA will post scan results automatically

Also supports Microsoft Teams via AGENTICQA_TEAMS_WEBHOOK_URL.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

import urllib.request
import urllib.error


@dataclass
class NotificationResult:
    """Result of a notification attempt."""
    sent: bool = False
    platform: str = ""
    error: str = ""
    status_code: int = 0


class SlackNotifier:
    """Send AgenticQA notifications to Slack."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        max_retries: int = 2,
        timeout: int = 10,
    ):
        self._url = webhook_url or os.getenv("AGENTICQA_SLACK_WEBHOOK_URL", "")
        self._max_retries = max_retries
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    def notify_scan(self, scan_output: dict) -> NotificationResult:
        """Post scan results to Slack."""
        if not self._url:
            return NotificationResult(error="AGENTICQA_SLACK_WEBHOOK_URL not set")

        summary = scan_output.get("summary", {})
        risk = summary.get("risk_level", "unknown")
        findings = summary.get("total_findings", 0)
        critical = summary.get("total_critical", 0)
        scanners_ok = summary.get("scanners_ok", 0)
        elapsed = summary.get("total_elapsed_s", 0)
        languages = summary.get("build_info", {}).get("languages", [])

        risk_emoji = {"critical": ":red_circle:", "high": ":large_orange_circle:",
                      "medium": ":large_yellow_circle:", "low": ":large_green_circle:"}.get(risk, ":white_circle:")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "AgenticQA Security Scan", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Risk Level:*\n{risk_emoji} {risk.upper()}"},
                    {"type": "mrkdwn", "text": f"*Findings:*\n{findings} total, {critical} critical"},
                    {"type": "mrkdwn", "text": f"*Scanners:*\n{scanners_ok} passed"},
                    {"type": "mrkdwn", "text": f"*Scan Time:*\n{elapsed}s"},
                ],
            },
        ]

        if languages:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":computer: Detected: {', '.join(languages)}"},
                ],
            })

        # Delta info if available
        delta = summary.get("delta")
        if delta:
            new_total = sum(d.get("new_findings", 0) for d in delta.values())
            new_crit = sum(d.get("new_critical", 0) for d in delta.values())
            if new_total == 0 and new_crit == 0:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": ":white_check_mark: *No new findings introduced*"},
                })
            else:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f":warning: *+{new_total} new findings* (+{new_crit} critical)"},
                })

        # Scanner breakdown
        scanners = scan_output.get("scanners", {})
        scanner_lines = []
        for name, data in scanners.items():
            if data.get("status") == "ok":
                r = data["result"]
                f_count = r.get("total_findings", r.get("findings_count", 0))
                c_count = r.get("critical", 0)
                icon = ":red_circle:" if c_count else ":white_check_mark:"
                scanner_lines.append(f"{icon} {name}: {f_count} findings")
        if scanner_lines:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Scanner Breakdown:*\n" + "\n".join(scanner_lines[:10])},
            })

        payload = {"blocks": blocks}
        return self._send(payload)

    def notify_trend_alert(
        self,
        direction: str,
        repo_id: str = "",
        current_findings: int = 0,
        delta: float = 0,
    ) -> NotificationResult:
        """Send a trend alert (e.g., findings worsening)."""
        if not self._url:
            return NotificationResult(error="AGENTICQA_SLACK_WEBHOOK_URL not set")

        if direction == "worsening":
            emoji = ":chart_with_upwards_trend:"
            text = f"Security findings are *worsening* (+{delta:.0f} avg findings)"
        elif direction == "improving":
            emoji = ":chart_with_downwards_trend:"
            text = f"Security findings are *improving* ({delta:.0f} avg findings)"
        else:
            return NotificationResult(error="No alert needed for stable trends")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *AgenticQA Trend Alert*\n{text}",
                },
            },
        ]
        if repo_id:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Repository: `{repo_id}`"}],
            })

        return self._send({"blocks": blocks})

    def notify_compliance_deadline(
        self,
        regulation: str,
        article: str,
        title: str,
        days_remaining: int,
    ) -> NotificationResult:
        """Send a compliance deadline alert."""
        if not self._url:
            return NotificationResult(error="AGENTICQA_SLACK_WEBHOOK_URL not set")

        if days_remaining > 90:
            return NotificationResult(error="Not urgent enough for alert")

        emoji = ":rotating_light:" if days_remaining <= 0 else ":alarm_clock:"
        urgency = "OVERDUE" if days_remaining <= 0 else f"{days_remaining} days remaining"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *Compliance Deadline Alert*\n"
                        f"*{regulation}* — {article}: {title}\n"
                        f"Status: *{urgency}*"
                    ),
                },
            },
        ]
        return self._send({"blocks": blocks})

    def _send(self, payload: dict) -> NotificationResult:
        """Send payload to Slack webhook with retry."""
        data = json.dumps(payload).encode()

        for attempt in range(self._max_retries + 1):
            try:
                req = urllib.request.Request(
                    self._url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    return NotificationResult(sent=True, platform="slack", status_code=resp.status)
            except urllib.error.HTTPError as e:
                if attempt == self._max_retries or e.code < 500:
                    return NotificationResult(error=f"HTTP {e.code}", status_code=e.code, platform="slack")
                time.sleep(2 ** attempt)
            except Exception as e:
                if attempt == self._max_retries:
                    return NotificationResult(error=str(e), platform="slack")
                time.sleep(2 ** attempt)

        return NotificationResult(error="Max retries exceeded", platform="slack")


class TeamsNotifier:
    """Send AgenticQA notifications to Microsoft Teams."""

    def __init__(self, webhook_url: Optional[str] = None, timeout: int = 10):
        self._url = webhook_url or os.getenv("AGENTICQA_TEAMS_WEBHOOK_URL", "")
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    def notify_scan(self, scan_output: dict) -> NotificationResult:
        """Post scan results to Teams."""
        if not self._url:
            return NotificationResult(error="AGENTICQA_TEAMS_WEBHOOK_URL not set")

        summary = scan_output.get("summary", {})
        risk = summary.get("risk_level", "unknown")
        findings = summary.get("total_findings", 0)
        critical = summary.get("total_critical", 0)

        color = {"critical": "FF0000", "high": "FF8C00", "medium": "FFD700", "low": "00FF00"}.get(risk, "808080")

        # Teams Adaptive Card
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"AgenticQA Scan: {risk.upper()} risk",
            "sections": [{
                "activityTitle": "AgenticQA Security Scan",
                "facts": [
                    {"name": "Risk Level", "value": risk.upper()},
                    {"name": "Total Findings", "value": str(findings)},
                    {"name": "Critical", "value": str(critical)},
                ],
                "markdown": True,
            }],
        }

        try:
            req = urllib.request.Request(
                self._url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return NotificationResult(sent=True, platform="teams", status_code=resp.status)
        except Exception as e:
            return NotificationResult(error=str(e), platform="teams")
