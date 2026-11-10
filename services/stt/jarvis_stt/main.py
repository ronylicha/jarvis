import logging
"""Jarvis STT FastAPI application."""

import json
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from jarvis_stt.config import settings
from jarvis_stt.whisper_wrapper import TranscriptionResult, WhisperError, transcribe

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
    logger.info("stt.startup", port=settings.port, model=str(settings.model_path_abs))
    yield
    logger.info("stt.shutdown")


app = FastAPI(title="Jarvis STT", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check — no filesystem paths exposed to clients."""
    binary_ok = settings.whisper_binary_abs.exists()
    model_ok = settings.model_path_abs.exists()
    status = "ok" if (binary_ok and model_ok) else "degraded"
    return {
        "status": status,
        "binary_exists": binary_ok,
        "model_exists": model_ok,
        "service": "jarvis-stt",
        "version": "0.1.0",
    }


@app.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    language: str | None = None,
):
    """Transcribe an uploaded audio file.

    Accepts wav, mp3, flac, ogg. Max size configurable via JARVIS_STT_MAX_AUDIO_SIZE_MB.
    Returns JSON with text, language and optional duration.
    """
    contents = await file.read()
    max_bytes = settings.max_audio_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large. Max {settings.max_audio_size_mb} MB.",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        result: TranscriptionResult = await transcribe(contents, language=language)
    except WhisperError as exc:
        # Log full error server-side, return generic message to client
        logger.error("stt.transcribe_error", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="Transcription failed. Check server logs for details.",
        )

    return JSONResponse(content={
        "text": result.text,
        "language": result.language,
        "duration": result.duration_seconds,
    })


@app.websocket("/transcribe-stream")
async def transcribe_stream(ws: WebSocket):
    """WebSocket endpoint for streaming transcription.

    Protocol:
    - Client sends binary audio chunks (enforced max size per config)
    - Client sends JSON {"action": "finalize"} to trigger transcription
    - Server responds with JSON {"text": "...", "language": "..."}
    """
    await ws.accept()
    buffer = bytearray()
    language: str | None = None
    max_bytes = settings.max_audio_size_mb * 1024 * 1024

    try:
        while True:
            message = await ws.receive()

            if "bytes" in message and message["bytes"]:
                buffer.extend(message["bytes"])
                # Defense-in-depth: enforce size limit on every chunk
                if len(buffer) > max_bytes:
                    await ws.send_json({
                        "error": f"Audio exceeds {settings.max_audio_size_mb} MB limit",
                    })
                    await ws.close(code=1009)
                    return

            elif "text" in message and message["text"]:
                try:
                    cmd = json.loads(message["text"])
                except json.JSONDecodeError:
                    await ws.send_json({"error": "Invalid JSON command"})
                    continue

                action = cmd.get("action")
                if action == "set_language":
                    language = cmd.get("language")
                    await ws.send_json({"status": "language_set", "language": language})

                elif action == "finalize":
                    if not buffer:
                        await ws.send_json({"error": "No audio data received"})
                        continue
                    try:
                        result = await transcribe(bytes(buffer), language=language)
                        await ws.send_json({
                            "text": result.text,
                            "language": result.language,
                        })
                    except WhisperError as exc:
                        # Log full error server-side only
                        logger.error("stt.stream_transcribe_error", error=str(exc))
                        await ws.send_json({
                            "error": "Transcription failed. Check server logs.",
                        })
                    buffer.clear()

                elif action == "reset":
                    buffer.clear()
                    await ws.send_json({"status": "buffer_cleared"})

                else:
                    await ws.send_json({"error": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        logger.info("stt.stream_disconnect")
    except Exception as exc:
        logger.error("stt.stream_error", error=str(exc))
        try:
            await ws.close(code=1011)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)