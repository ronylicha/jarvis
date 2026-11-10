import logging
"""Jarvis TTS FastAPI application."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from jarvis_tts.config import settings
from jarvis_tts.piper_wrapper import PiperError, SynthesisResult, list_available_voices, synthesize

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    logger.info("tts.startup", port=settings.port, default_voice=settings.default_voice)
    yield
    logger.info("tts.shutdown")


app = FastAPI(title="Jarvis TTS", version="0.1.0", lifespan=lifespan)


class SpeakRequest(BaseModel):
    """Request body for /speak endpoint."""

    text: str = Field(..., min_length=1, max_length=5000)
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@app.get("/health")
async def health():
    """Health check — no filesystem paths exposed to clients."""
    binary_ok = settings.piper_binary_abs.exists()
    voices = list_available_voices()
    status = "ok" if (binary_ok and len(voices) > 0) else "degraded"
    return {
        "status": status,
        "binary_exists": binary_ok,
        "voices_count": len(voices),
        "default_voice": settings.default_voice,
        "service": "jarvis-tts",
        "version": "0.1.0",
    }


@app.get("/voices")
async def voices():
    """List available TTS voices with metadata."""
    return {"voices": list_available_voices()}


@app.post("/speak")
async def speak(request: SpeakRequest):
    """Synthesize speech from text, return WAV audio.

    Returns audio/wav content-type. Use Accept header or Content-Disposition
    to handle the binary response.
    """
    try:
        result: SynthesisResult = await synthesize(
            request.text,
            voice=request.voice,
            speed=request.speed,
        )
    except PiperError as exc:
        # Log full error server-side, return generic message to client
        logger.error("tts.synthesize_error", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="Speech synthesis failed. Check server logs for details.",
        )

    return Response(
        content=result.audio_bytes,
        media_type="audio/wav",
        headers={
            "X-Voice": result.voice,
            "X-Sample-Rate": str(result.sample_rate),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)