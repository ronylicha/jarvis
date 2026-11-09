"""Subprocess wrapper for whisper.cpp binary."""

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

from jarvis_stt.config import settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TranscriptionResult:
    """Result of a whisper.cpp transcription."""

    text: str
    language: str
    duration_seconds: float | None = None


class WhisperError(Exception):
    """Raised when whisper.cpp subprocess fails."""


async def transcribe(
    audio_bytes: bytes,
    *,
    language: str | None = None,
    timeout: int | None = None,
) -> TranscriptionResult:
    """Transcribe audio bytes using whisper.cpp subprocess.

    Args:
        audio_bytes: Raw audio file content (wav/mp3/flac).
        language: Language code override (default: config default_language).
        timeout: Timeout in seconds (default: config timeout_seconds).

    Returns:
        TranscriptionResult with text, detected language and duration.

    Raises:
        WhisperError: If binary missing, model missing, or subprocess fails.
    """
    binary = settings.whisper_binary_abs
    model = settings.model_path_abs

    if not binary.exists():
        raise WhisperError(
            f"whisper.cpp binary not found at {binary}. "
            "Run scripts/build_whisper.sh first."
        )
    if not model.exists():
        raise WhisperError(
            f"Model not found at {model}. "
            "Run scripts/download_model.sh first."
        )

    lang = language or settings.default_language
    tout = timeout or settings.timeout_seconds

    # Write audio to temp file (whisper.cpp reads from disk)
    suffix = _detect_extension(audio_bytes)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            str(binary),
            "-m", str(model),
            "-f", str(tmp_path),
            "--language", lang,
            "-t", str(settings.threads),
            "--no-timestamps",
            "-np",  # no progress
        ]

        logger.info("whisper.transcribe_start", language=lang, size=len(audio_bytes))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=tout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise WhisperError(f"Transcription timed out after {tout}s")

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            raise WhisperError(f"whisper.cpp failed (exit {proc.returncode}): {err_msg}")

        text = stdout.decode(errors="replace").strip()
        # whisper.cpp outputs lines like "[00:00:00.000 --> 00:00:05.000]   text"
        # With --no-timestamps it's just plain text lines
        clean_text = "\n".join(
            line.strip() for line in text.splitlines() if line.strip()
        )

        logger.info("whisper.transcribe_done", chars=len(clean_text))
        return TranscriptionResult(text=clean_text, language=lang)

    finally:
        tmp_path.unlink(missing_ok=True)


def _detect_extension(data: bytes) -> str:
    """Detect audio format from magic bytes."""
    if data[:4] == b"RIFF":
        return ".wav"
    if data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
        return ".mp3"
    if data[:4] == b"fLaC":
        return ".flac"
    if data[:4] == b"OggS":
        return ".ogg"
    return ".wav"  # fallback