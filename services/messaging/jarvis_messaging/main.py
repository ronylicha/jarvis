"""Jarvis Messaging FastAPI application."""

import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from jarvis_messaging.config import settings
from jarvis_messaging.handlers import (
    fetch_email_messages,
    fetch_telegram_messages,
    fetch_whatsapp_messages,
    get_channel_statuses,
    send_email,
    send_telegram_message,
    send_whatsapp_message,
)

logger = structlog.get_logger(__name__)


# --- Auth ---

async def verify_token(x_jarvis_token: str = Header(default="")) -> str:
    """Verify bearer token. Fail-closed: rejects when token unset or empty.

    Set JARVIS_MESSAGING_API_TOKEN to enable the service.
    Without it, every request returns 403 to prevent accidental exposure.
    Empty string is treated as misconfiguration (500), not disabled auth.
    """
    raw = os.environ.get("JARVIS_MESSAGING_API_TOKEN")
    if raw is None:
        raise HTTPException(
            status_code=403,
            detail="Messaging service requires JARVIS_MESSAGING_API_TOKEN to be set.",
        )
    if not raw:
        raise HTTPException(
            status_code=500,
            detail="JARVIS_MESSAGING_API_TOKEN is set but empty. Fix configuration or unset the variable.",
        )
    if not x_jarvis_token or not hmac.compare_digest(x_jarvis_token, raw):
        raise HTTPException(status_code=403, detail="Invalid or missing token")
    return "__authenticated__"


@asynccontextmanager
async def lifespan(app: FastAPI):
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logger.level),
    )
    logger.info("messaging.startup", port=settings.port)
    yield
    logger.info("messaging.shutdown")


app = FastAPI(title="Jarvis Messaging", version="0.1.0", lifespan=lifespan)


# --- Models ---

class SendMessageRequest(BaseModel):
    channel: str = Field(..., pattern="^(telegram|whatsapp|email)$")
    to: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1, max_length=10000)
    subject: str | None = None  # email only


# --- Endpoints ---

@app.get("/health")
async def health():
    """Static health check."""
    return {"status": "ok", "service": "jarvis-messaging", "version": "0.1.0"}


@app.get("/channels", dependencies=[Depends(verify_token)])
async def channels():
    """Get status of all messaging channels."""
    return {"channels": get_channel_statuses()}


@app.get("/inbox", dependencies=[Depends(verify_token)])
async def inbox(channel: str | None = None):
    """Fetch incoming messages from configured channels.

    Optional query param `channel` filters to one channel (telegram|whatsapp|email).
    """
    messages: list[dict[str, Any]] = []

    if channel is None or channel == "telegram":
        tg = await fetch_telegram_messages()
        messages.extend([
            {
                "channel": m.channel, "sender": m.sender, "content": m.content,
                "timestamp": m.timestamp, "message_id": m.message_id,
                "subject": m.subject,
            }
            for m in tg
        ])

    if channel is None or channel == "whatsapp":
        wa = await fetch_whatsapp_messages()
        messages.extend([
            {
                "channel": m.channel, "sender": m.sender, "content": m.content,
                "timestamp": m.timestamp, "message_id": m.message_id,
            }
            for m in wa
        ])

    if channel is None or channel == "email":
        loop = asyncio.get_event_loop()
        em = await loop.run_in_executor(None, fetch_email_messages)
        messages.extend([
            {
                "channel": m.channel, "sender": m.sender, "content": m.content,
                "timestamp": m.timestamp, "message_id": m.message_id,
                "subject": m.subject,
            }
            for m in em
        ])

    return {"messages": messages, "count": len(messages)}


@app.post("/send", dependencies=[Depends(verify_token)])
async def send(request: SendMessageRequest):
    """Send a message via the specified channel."""
    success = False

    if request.channel == "telegram":
        success = await send_telegram_message(request.to, request.content)
    elif request.channel == "whatsapp":
        success = await send_whatsapp_message(request.to, request.content)
    elif request.channel == "email":
        if not request.subject:
            raise HTTPException(status_code=400, detail="Email requires 'subject' field")
        success = await send_email(request.to, request.subject, request.content)

    if not success:
        raise HTTPException(status_code=503, detail=f"Failed to send via {request.channel}")

    return {"status": "sent", "channel": request.channel, "to": request.to}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)