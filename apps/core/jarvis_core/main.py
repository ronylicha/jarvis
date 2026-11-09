"""Jarvis Core FastAPI application — LLM router + orchestration hub."""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from jarvis_core.config import settings
from jarvis_core.llm_router import LLMResponse, LLMRouter, LLMRouterError

logger = structlog.get_logger(__name__)

router = LLMRouter()


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
    logger.info("core.startup", port=settings.port, default_provider=settings.default_provider)
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


@app.post("/chat")
async def chat(request: ChatRequest):
    """Route a chat completion request to an LLM provider.

    Specify provider explicitly or use the configured default.
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)