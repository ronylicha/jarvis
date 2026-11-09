"""Jarvis Agent Sessions FastAPI application."""

import asyncio
import hmac
import json
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from jarvis_agent_sessions.config import settings
from jarvis_agent_sessions.scanner import scan_all_sessions

logger = structlog.get_logger(__name__)


# --- Auth ---

async def verify_token(x_jarvis_token: str = Header(default="")) -> str:
    """Verify bearer token. Fail-closed when JARVIS_AGENT_SESSIONS_API_TOKEN is set."""
    expected = os.environ.get("JARVIS_AGENT_SESSIONS_API_TOKEN")
    if expected is None:
        return "__anonymous__"
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="JARVIS_AGENT_SESSIONS_API_TOKEN is set but empty.",
        )
    if not x_jarvis_token or not hmac.compare_digest(x_jarvis_token, expected):
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
    logger.info("agent_sessions.startup", port=settings.port)
    yield
    logger.info("agent_sessions.shutdown")


app = FastAPI(title="Jarvis Agent Sessions", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Static health check — no session scanning to avoid info disclosure.

    Detailed status (sessions, proxy relay) requires authentication via /sessions.
    """
    return {
        "status": "ok",
        "service": "jarvis-agent-sessions",
        "version": "0.1.0",
    }


@app.get("/sessions", dependencies=[Depends(verify_token)])
async def get_sessions():
    """Get all active agent sessions (Claude, Codex, Kimi, ZAI)."""
    try:
        return scan_all_sessions()
    except Exception as exc:
        logger.error("agent_sessions.scan_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Session scan failed.")


@app.get("/sessions/stream", dependencies=[Depends(verify_token)])
async def sessions_stream():
    """SSE endpoint for real-time session updates.

    Emits session snapshots every scan_interval_seconds.
    Format: data: {"sessions": [...], "total_active": N}\n\n
    """
    async def event_generator():
        while True:
            try:
                data = scan_all_sessions()
                event = json.dumps(data, default=str)
                yield f"data: {event}\n\n"
            except Exception as exc:
                logger.error("agent_sessions.stream_error", error=str(exc))
                error_event = json.dumps({"error": "Scan failed", "sessions": []})
                yield f"data: {error_event}\n\n"

            await asyncio.sleep(settings.scan_interval_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/proxy/status", dependencies=[Depends(verify_token)])
async def proxy_status():
    """Check ghostcli proxy relay status and token counting configuration."""
    from jarvis_agent_sessions.scanner import _find_ghostcli_relay

    relay = _find_ghostcli_relay()
    return {
        "relay_active": relay is not None,
        "relay": relay,
        "ghostcli_base_url": settings.ghostcli_base_url,
        "usage_shim_url": settings.usage_shim_url,
        "note": "Token counting passes through the relay when active. "
                "Configure JARVIS_AGENT_SESSIONS_GHOSTCLI_API_KEY for direct access.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)