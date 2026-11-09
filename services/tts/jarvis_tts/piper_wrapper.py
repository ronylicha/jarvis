"""Subprocess wrapper for Piper TTS binary."""

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

from jarvis_tts.config import settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SynthesisResult:
    """Result of a Piper TTS synthesis."""

    audio_bytes: bytes
    voice: str
    sample_rate: int = 22050


class PiperError(Exception):
    """Raised when Piper subprocess fails."""


async def synthesize(
    text: str,
    *,
    voice: str | None = None,
    speed: float | None = None,
    timeout: int | None = None,
) -> SynthesisResult:
    """Synthesize speech from text using Piper TTS subprocess.

    Args:
        text: Text to synthesize.
        voice: Voice name override (default: config default_voice).
        speed: Speed multiplier 0.5-2.0 (default: config default_speed).
        timeout: Timeout in seconds (default: config timeout_seconds).

    Returns:
        SynthesisResult with WAV audio bytes.

    Raises:
        PiperError: If binary missing, model missing, or subprocess fails.
    """
    binary = settings.piper_binary_abs
    voice_name = voice or settings.default_voice
    spd = speed or settings.default_speed
    tout = timeout or settings.timeout_seconds

    if not binary.exists():
        raise PiperError(
            f"Piper binary not found at {binary}. "
            "Run scripts/install_piper.sh first."
        )

    model_path = settings.voices_dir_abs / f"{voice_name}.onnx"
    if not model_path.exists():
        raise PiperError(
            f"Voice model not found at {model_path}. "
            "Run scripts/download_voices.sh first."
        )

    # Clamp speed
    spd = max(settings.min_speed, min(settings.max_speed, spd))

    # Piper length_scale: 1.0 = normal, <1 = faster, >1 = slower
    # User speed: 2.0 = fast → length_scale = 0.5
    length_scale = 1.0 / spd

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            str(binary),
            "--model", str(model_path),
            "--output_file", str(tmp_path),
            "--length_scale", str(length_scale),
            "--noise_scale", "0.667",
            "--noise_w", "0.8",
        ]

        logger.info("piper.synthesize_start", voice=voice_name, chars=len(text))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=text.encode("utf-8")),
                timeout=tout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise PiperError(f"Synthesis timed out after {tout}s")

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            raise PiperError(f"Piper failed (exit {proc.returncode}): {err_msg}")

        audio = tmp_path.read_bytes()
        if len(audio) == 0:
            raise PiperError("Piper produced empty audio output")

        logger.info("piper.synthesize_done", audio_bytes=len(audio))
        return SynthesisResult(audio_bytes=audio, voice=voice_name)

    finally:
        tmp_path.unlink(missing_ok=True)


def list_available_voices() -> list[dict]:
    """Scan voices directory and return metadata for each available voice."""
    voices_dir = settings.voices_dir_abs
    if not voices_dir.exists():
        return []

    voices = []
    for onnx_file in sorted(voices_dir.glob("*.onnx")):
        name = onnx_file.stem
        config_file = voices_dir / f"{name}.onnx.json"
        meta = {"name": name, "model_size_mb": round(onnx_file.stat().st_size / 1024 / 1024, 1)}

        if config_file.exists():
            import json
            try:
                cfg = json.loads(config_file.read_text())
                meta["language"] = cfg.get("language", {}).get("name_english", "unknown")
                meta["sample_rate"] = cfg.get("audio", {}).get("sample_rate", 22050)
            except (json.JSONDecodeError, KeyError):
                pass

        voices.append(meta)

    return voices