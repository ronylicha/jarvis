"""Channel handlers for Telegram, WhatsApp Business, and Email."""

import asyncio
import email
import imaplib
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

import httpx
import structlog

from jarvis_messaging.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class IncomingMessage:
    """Unified incoming message from any channel."""

    channel: str  # telegram, whatsapp, email
    sender: str
    content: str
    timestamp: str
    message_id: str | None = None
    subject: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Telegram ---

async def fetch_telegram_messages() -> list[IncomingMessage]:
    """Fetch new messages from Telegram Bot API using getUpdates."""
    if not settings.telegram_bot_token:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates",
                params={"limit": 20, "timeout": 0},
            )
            resp.raise_for_status()
            data = resp.json()

        messages = []
        for update in data.get("result", []):
            msg = update.get("message")
            if not msg or "text" not in msg:
                continue

            chat = msg.get("chat", {})
            sender_name = chat.get("first_name", "") or chat.get("title", "Unknown")
            sender_id = str(chat.get("id", ""))

            messages.append(IncomingMessage(
                channel="telegram",
                sender=f"{sender_name} ({sender_id})",
                content=msg["text"],
                timestamp=datetime.fromtimestamp(
                    msg.get("date", 0), tz=timezone.utc
                ).isoformat(),
                message_id=str(msg.get("message_id", "")),
                metadata={"chat_id": sender_id, "update_id": update.get("update_id")},
            ))

        logger.info("telegram.fetched", count=len(messages))
        return messages

    except Exception as exc:
        logger.error("telegram.fetch_error", error=str(exc))
        return []


async def send_telegram_message(chat_id: str, text: str) -> bool:
    """Send a plain-text message via Telegram Bot API.

    No parse_mode is used to avoid Markdown injection vulnerabilities.
    Text is sent as-is without formatting interpretation by Telegram.
    """
    if not settings.telegram_bot_token:
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            resp.raise_for_status()
        logger.info("telegram.sent", chat_id=chat_id)
        return True
    except Exception as exc:
        logger.error("telegram.send_error", error=str(exc))
        return False


# --- WhatsApp Business ---

async def fetch_whatsapp_messages() -> list[IncomingMessage]:
    """Fetch messages from WhatsApp Business Cloud API."""
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return []

    try:
        url = (
            f"{settings.whatsapp_base_url}/{settings.whatsapp_api_version}"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        messages = []
        for msg in data.get("data", []):
            if msg.get("status") == "read":
                continue
            messages.append(IncomingMessage(
                channel="whatsapp",
                sender=msg.get("from", "unknown"),
                content=msg.get("body", ""),
                timestamp=msg.get("timestamp", ""),
                message_id=msg.get("id"),
            ))

        logger.info("whatsapp.fetched", count=len(messages))
        return messages

    except Exception as exc:
        logger.error("whatsapp.fetch_error", error=str(exc))
        return []


async def send_whatsapp_message(to: str, text: str) -> bool:
    """Send a text message via WhatsApp Business Cloud API."""
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return False

    try:
        url = (
            f"{settings.whatsapp_base_url}/{settings.whatsapp_api_version}"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text},
                },
            )
            resp.raise_for_status()
        logger.info("whatsapp.sent", to=to)
        return True
    except Exception as exc:
        logger.error("whatsapp.send_error", error=str(exc))
        return False


# --- Email IMAP/SMTP ---

def fetch_email_messages() -> list[IncomingMessage]:
    """Fetch recent unread emails via IMAP (synchronous — run in executor)."""
    if not settings.email_imap_host or not settings.email_imap_user:
        return []

    try:
        conn = imaplib.IMAP4_SSL(settings.email_imap_host, settings.email_imap_port)
        conn.login(settings.email_imap_user, settings.email_imap_pass)
        conn.select("INBOX")

        status, msg_nums = conn.search(None, "UNSEEN")
        if status != "OK":
            conn.logout()
            return []

        ids = msg_nums[0].split()[:settings.email_max_fetch]
        messages = []

        for num in ids:
            status, msg_data = conn.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode(errors="replace")
                        break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="replace")

            messages.append(IncomingMessage(
                channel="email",
                sender=msg.get("From", "unknown"),
                content=body[:2000],
                timestamp=msg.get("Date", ""),
                message_id=msg.get("Message-ID"),
                subject=msg.get("Subject", ""),
            ))

        conn.logout()
        logger.info("email.fetched", count=len(messages))
        return messages

    except Exception as exc:
        logger.error("email.fetch_error", error=str(exc))
        return []


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via SMTP."""
    if not settings.email_smtp_host or not settings.email_smtp_user:
        return False

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = settings.email_smtp_user
        msg["To"] = to
        msg["Subject"] = subject

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send, msg)
        logger.info("email.sent", to=to, subject=subject)
        return True
    except Exception as exc:
        logger.error("email.send_error", error=str(exc))
        return False


def _smtp_send(msg: MIMEText) -> None:
    """Synchronous SMTP send (runs in thread executor)."""
    with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.email_smtp_user, settings.email_smtp_pass)
        server.send_message(msg)


# --- Channel status ---

def get_channel_statuses() -> dict[str, dict[str, Any]]:
    """Return connection status for each messaging channel."""
    return {
        "telegram": {
            "configured": bool(settings.telegram_bot_token),
            "chat_id_set": bool(settings.telegram_chat_id),
        },
        "whatsapp": {
            "configured": bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id),
        },
        "email": {
            "configured": bool(settings.email_imap_host and settings.email_imap_user),
            "smtp_configured": bool(settings.email_smtp_host and settings.email_smtp_user),
        },
    }