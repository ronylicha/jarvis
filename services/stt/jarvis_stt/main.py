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
        wrapper_class=structlog.make_filtering_bound_logger(logger.level),
    )
    logger.info("stt.startup", port=settings.port, model=str(settings.model_path_abs))
    yield
    logger.info("stt.shutdown")


app = FastAPI(title="Jarvis STT", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check with binary and model status."""
    binary_ok = settings.whisper_binary_abs.exists()
    model_ok = settings.model_path_abs.exists()
    status = "ok" if (binary_ok and model_ok) else "degraded"
    return {
        "status": status,
        "binary_exists": binary_ok,
        "binary_path": str(settings.whisper_binary_abs),
        "model_exists": model_ok,
        "model_path": str(settings.model_path_abs),
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
            detail=f"Audio too large ({len(contents)} bytes). Max {settings.max_audio_size_mb} MB.",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        result: TranscriptionResult = await transcribe(contents, language=language)
    except WhisperError as exc:
        logger.error("stt.transcribe_error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))

    return JSONResponse(content={
        "text": result.text,
        "language": result.language,
        "duration": result.duration_seconds,
    })


@app.websocket("/transcribe-stream")
async def transcribe_stream(ws: WebSocket):
    """WebSocket endpoint for streaming transcription.

    Protocol:
      - Client sends binary audio chunks
      - Client sends JSON {"action": "finalize"} to trigger transcription
      - Server responds with JSON {"text": "...", "language": "..."}
    """
    await ws.accept()
    buffer = bytearray()
    language: str | None = None

    try:
        while True:
            message = await ws.receive()

            if "bytes" in message and message["bytes"]:
                buffer.extend(message["bytes"])

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
                        await ws.send_json({"error": str(exc)})
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
        await ws.close(code=1011)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)