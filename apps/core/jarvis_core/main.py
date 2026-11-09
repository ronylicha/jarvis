"""Jarvis Core FastAPI application — LLM router + orchestration hub."""

import asyncio
import hmac
import json
import os
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from jarvis_core.config import settings
from jarvis_core.llm_router import LLMResponse, LLMRouter, LLMRouterError

logger = structlog.get_logger(__name__)

router = LLMRouter()


# --- Auth for /chat (fail-closed when token configured) ---

async def verify_chat_token(x_jarvis_token: str = Header(default="")) -> str:
    """Verify bearer token for /chat endpoint.

    Fail-closed: if JARVIS_CORE_API_TOKEN is set but empty, reject all requests
    (misconfiguration, not "auth disabled"). Only truly unset env var disables auth.
    """
    raw = os.environ.get("JARVIS_CORE_API_TOKEN")
    if raw is None:
        # Env var truly unset → local dev mode, no auth required
        return "__anonymous__"
    if not raw:
        # Env var set to empty string → misconfiguration, refuse all requests
        raise HTTPException(
            status_code=500,
            detail="JARVIS_CORE_API_TOKEN is set but empty. Fix configuration or unset the variable.",
        )
    if not x_jarvis_token or not hmac.compare_digest(x_jarvis_token, raw):
        raise HTTPException(status_code=403, detail="Invalid or missing token")
    return "__authenticated__"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logger.level),
    )
    auth_mode = "disabled" if os.environ.get("JARVIS_CORE_API_TOKEN") is None else "enabled"
    logger.info("core.startup", port=settings.port, default_provider=settings.default_provider, auth=auth_mode)
    yield
    await router.close()
    logger.info("core.shutdown")


app = FastAPI(title="Jarvis Core", version="0.1.0", lifespan=lifespan)


# --- Request/Response models ---


class ChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


# --- Endpoints ---


@app.get("/health")
async def health():
    """Health check with provider status."""
    providers = router.get_available_providers()
    configured_count = sum(1 for p in providers if p["configured"])
    return {
        "status": "ok" if configured_count > 0 else "degraded",
        "providers": providers,
        "default_provider": settings.default_provider,
        "service": "jarvis-core",
        "version": "0.1.0",
    }


@app.get("/providers")
async def list_providers():
    """List available LLM providers and their configuration status."""
    return {"providers": router.get_available_providers()}


@app.post("/chat", dependencies=[Depends(verify_chat_token)])
async def chat(request: ChatRequest):
    """Route a chat completion request to an LLM provider.

    Requires X-Jarvis-Token header when JARVIS_CORE_API_TOKEN is set.
    Messages follow OpenAI format: [{"role": "user", "content": "..."}]
    """
    try:
        result: LLMResponse = await router.chat(
            messages=request.messages,
            provider=request.provider,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
    except LLMRouterError as exc:
        logger.error("core.chat_error", error=str(exc))
        raise HTTPException(status_code=503, detail="LLM request failed. Check server logs.")

    response: dict[str, Any] = {
        "content": result.content,
        "provider": result.provider,
        "model": result.model,
    }
    if result.usage:
        response["usage"] = result.usage

    return response


# Concurrency limiter for streaming endpoint — prevents resource amplification
_stream_semaphore = asyncio.Semaphore(5)


@app.post("/chat/stream", dependencies=[Depends(verify_chat_token)])
async def chat_stream(request: ChatRequest):
    """Streaming SSE endpoint for chat completions.

    NOTE: Current implementation uses simulated streaming (full response
    buffered server-side, then chunked to client). True provider-native
    streaming requires per-provider stream=True support in llm_router.
    This is a known limitation tracked for future improvement.

    Security measures:
    - Concurrency limited to 5 simultaneous streams via semaphore
    - Error details logged server-side only; generic message sent to client
    - Single SSE event emitted (no artificial chunking/delays)
    """
    async def event_generator():
        async with _stream_semaphore:
            try:
                result: LLMResponse = await router.chat(
                    messages=request.messages,
                    provider=request.provider,
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )

                # Emit complete response in single event (no fake chunking)
                event = json.dumps({
                    "content": result.content,
                    "done": True,
                    "provider": result.provider,
                    "model": result.model,
                    "usage": result.usage,
                })
                yield f"data: {event}\n\n"

            except LLMRouterError as exc:
                # SECURITY: log full error server-side, send generic message to client
                logger.error("core.stream_error", error=str(exc))
                error_event = json.dumps({
                    "error": "LLM request failed. Check server logs.",
                    "done": True,
                })
                yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)