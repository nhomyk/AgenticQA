"""Safe mail client for the AgenticQA workspace.

Reading email is a safe (read-only) operation.
Sending email is classified as IRREVERSIBLE and requires approval through
the DestructiveActionInterceptor.

Credentials are **never** stored in plaintext — they come from environment
variables or a provider-config dict passed at runtime.
"""
from __future__ import annotations

import email
import email.utils
import imaplib
import smtplib
import time
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional


# ── Data types ───────────────────────────────────────────────────────────────


@dataclass
class MailMessage:
    """A single email message (read-only representation)."""
    uid: str = ""
    subject: str = ""
    sender: str = ""
    to: str = ""
    date: str = ""
    body_plain: str = ""
    body_html: str = ""
    has_attachments: bool = False
    folder: str = "INBOX"


@dataclass
class MailConfig:
    """IMAP/SMTP connection parameters.

    All fields may be supplied via env vars:
      AGENTICQA_MAIL_IMAP_HOST, AGENTICQA_MAIL_IMAP_PORT,
      AGENTICQA_MAIL_SMTP_HOST, AGENTICQA_MAIL_SMTP_PORT,
      AGENTICQA_MAIL_USER, AGENTICQA_MAIL_PASSWORD
    """
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    user: str = ""
    password: str = ""
    use_ssl: bool = True

    @classmethod
    def from_env(cls) -> "MailConfig":
        import os
        return cls(
            imap_host=os.getenv("AGENTICQA_MAIL_IMAP_HOST", ""),
            imap_port=int(os.getenv("AGENTICQA_MAIL_IMAP_PORT", "993")),
            smtp_host=os.getenv("AGENTICQA_MAIL_SMTP_HOST", ""),
            smtp_port=int(os.getenv("AGENTICQA_MAIL_SMTP_PORT", "587")),
            user=os.getenv("AGENTICQA_MAIL_USER", ""),
            password=os.getenv("AGENTICQA_MAIL_PASSWORD", ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.imap_host and self.user and self.password)


@dataclass
class MailOpResult:
    """Result of a mail operation."""
    success: bool
    action: str  # list_folders, list_messages, read, send
    error: Optional[str] = None
    data: Any = None
    requires_approval: bool = False
    approval_token: Optional[str] = None


# ── Safe mail client ─────────────────────────────────────────────────────────


class SafeMailClient:
    """IMAP/SMTP client with safety gates.

    - read operations (list, fetch) → always allowed
    - send operations → blocked until approved
    """

    def __init__(self, config: Optional[MailConfig] = None) -> None:
        self.config = config or MailConfig.from_env()
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    # ── connection helpers ────────────────────────────────────────────────

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        if self._imap is not None:
            try:
                self._imap.noop()
                return self._imap
            except Exception:
                self._imap = None

        conn = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)
        conn.login(self.config.user, self.config.password)
        self._imap = conn
        return conn

    def close(self) -> None:
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    # ── read operations (safe) ────────────────────────────────────────────

    def list_folders(self) -> MailOpResult:
        """List available IMAP folders."""
        if not self.config.is_configured:
            return MailOpResult(success=False, action="list_folders",
                                error="Mail not configured")
        try:
            conn = self._connect_imap()
            status, folder_data = conn.list()
            if status != "OK":
                return MailOpResult(success=False, action="list_folders",
                                    error=f"IMAP LIST failed: {status}")
            folders: List[str] = []
            for item in (folder_data or []):
                if isinstance(item, bytes):
                    parts = item.decode("utf-8", errors="replace").split('"')
                    if len(parts) >= 3:
                        folders.append(parts[-2])
                    else:
                        folders.append(item.decode("utf-8", errors="replace"))
            return MailOpResult(success=True, action="list_folders", data=folders)
        except Exception as exc:
            return MailOpResult(success=False, action="list_folders",
                                error=str(exc))

    def list_messages(self, folder: str = "INBOX",
                      limit: int = 25) -> MailOpResult:
        """List recent message headers from *folder*."""
        if not self.config.is_configured:
            return MailOpResult(success=False, action="list_messages",
                                error="Mail not configured")
        try:
            conn = self._connect_imap()
            conn.select(folder, readonly=True)
            status, data = conn.search(None, "ALL")
            if status != "OK":
                return MailOpResult(success=False, action="list_messages",
                                    error=f"IMAP SEARCH failed: {status}")

            uids = (data[0] or b"").split()
            uids = uids[-limit:]  # most recent N

            messages: List[Dict[str, str]] = []
            for uid in reversed(uids):
                status2, msg_data = conn.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if status2 != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0]
                if isinstance(raw, tuple) and len(raw) >= 2:
                    header_bytes = raw[1]
                else:
                    continue
                msg = email.message_from_bytes(header_bytes)
                messages.append({
                    "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "subject": str(msg.get("Subject", "(no subject)")),
                    "from": str(msg.get("From", "")),
                    "date": str(msg.get("Date", "")),
                    "folder": folder,
                })

            return MailOpResult(success=True, action="list_messages",
                                data=messages)
        except Exception as exc:
            return MailOpResult(success=False, action="list_messages",
                                error=str(exc))

    def read_message(self, uid: str, folder: str = "INBOX") -> MailOpResult:
        """Fetch full message by UID."""
        if not self.config.is_configured:
            return MailOpResult(success=False, action="read",
                                error="Mail not configured")
        try:
            conn = self._connect_imap()
            conn.select(folder, readonly=True)
            status, msg_data = conn.fetch(uid.encode(), "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                return MailOpResult(success=False, action="read",
                                    error="Message not found")

            raw = msg_data[0]
            if isinstance(raw, tuple) and len(raw) >= 2:
                raw_bytes = raw[1]
            else:
                return MailOpResult(success=False, action="read",
                                    error="Unexpected IMAP response format")

            parsed = email.message_from_bytes(raw_bytes)

            body_plain = ""
            body_html = ""
            has_attachments = False

            if parsed.is_multipart():
                for part in parsed.walk():
                    ct = part.get_content_type()
                    disp = str(part.get("Content-Disposition", ""))
                    if "attachment" in disp:
                        has_attachments = True
                        continue
                    if ct == "text/plain" and not body_plain:
                        body_plain = part.get_payload(decode=True).decode(
                            "utf-8", errors="replace")
                    elif ct == "text/html" and not body_html:
                        body_html = part.get_payload(decode=True).decode(
                            "utf-8", errors="replace")
            else:
                payload = parsed.get_payload(decode=True)
                if payload:
                    body_plain = payload.decode("utf-8", errors="replace")

            msg = MailMessage(
                uid=uid,
                subject=str(parsed.get("Subject", "")),
                sender=str(parsed.get("From", "")),
                to=str(parsed.get("To", "")),
                date=str(parsed.get("Date", "")),
                body_plain=body_plain,
                body_html=body_html,
                has_attachments=has_attachments,
                folder=folder,
            )

            return MailOpResult(success=True, action="read", data=msg)
        except Exception as exc:
            return MailOpResult(success=False, action="read", error=str(exc))

    # ── destructive operations (HARD BLOCKED) ───────────────────────────────
    #
    # Email deletion is never exposed as an API.  This is a deliberate
    # design choice inspired by the Meta/OpenClaw incident (2026-02-23)
    # where an AI agent "speed-ran deleting" a safety director's inbox
    # after context-window compaction dropped the "don't take action"
    # instruction.  By not implementing delete/move/archive at all,
    # the workspace cannot lose emails even if every other safety layer
    # is bypassed.

    def delete_message(self, uid: str, folder: str = "INBOX") -> MailOpResult:
        """HARD BLOCKED — email deletion is never allowed.

        This method exists only so callers get a clear error instead of
        an AttributeError.  No code path can override the block.
        """
        return MailOpResult(
            success=False,
            action="delete",
            error=(
                "Email deletion is permanently disabled. "
                "This workspace is designed to never lose your emails. "
                "See: Meta/OpenClaw incident (2026-02-23)."
            ),
        )

    def move_message(self, uid: str, to_folder: str,
                     folder: str = "INBOX") -> MailOpResult:
        """HARD BLOCKED — email moves/archive are not allowed."""
        return MailOpResult(
            success=False,
            action="move",
            error=(
                "Email move/archive is disabled. "
                "Workspace mail access is read-only + compose."
            ),
        )

    # ── send operations (requires approval) ───────────────────────────────

    def compose_draft(self, to: str, subject: str,
                      body: str) -> Dict[str, str]:
        """Build a draft dict (does NOT send). Safe operation."""
        return {
            "from": self.config.user,
            "to": to,
            "subject": subject,
            "body": body,
            "timestamp": email.utils.formatdate(localtime=True),
        }

    def send_message(self, to: str, subject: str, body: str,
                     *, approved: bool = False) -> MailOpResult:
        """Send an email. Blocked unless *approved* is True.

        The caller (workspace safety layer) must set approved=True
        only after the DestructiveActionInterceptor has issued an
        approval token.
        """
        if not approved:
            return MailOpResult(
                success=False, action="send",
                error="Send requires approval — action classified as IRREVERSIBLE",
                requires_approval=True,
            )

        if not self.config.smtp_host:
            return MailOpResult(success=False, action="send",
                                error="SMTP not configured")

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.config.user
            msg["To"] = to
            msg["Subject"] = subject
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_ssl:
                    server.starttls()
                server.login(self.config.user, self.config.password)
                server.send_message(msg)

            return MailOpResult(success=True, action="send",
                                data={"to": to, "subject": subject})
        except Exception as exc:
            return MailOpResult(success=False, action="send", error=str(exc))
