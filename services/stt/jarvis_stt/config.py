"""Configuration for Jarvis STT service."""

from pathlib import Path

from pydantic_settings import BaseSettings


class STTSettings(BaseSettings):
    """STT service configuration loaded from environment / .env."""

    # Paths (relative to project root ~/projects/jarvis/)
    project_root: Path = Path.home() / "projects" / "jarvis"
    whisper_binary: Path = Path("bin/whisper.cpp/build/bin/whisper-cli")
    model_path: Path = Path("models/ggml-small.bin")

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Inference
    default_language: str = "fr"
    timeout_seconds: int = 30
    max_audio_size_mb: int = 25
    threads: int = 4  # i7-1360P has 12c/16t, leave headroom for other services

    @property
    def whisper_binary_abs(self) -> Path:
        return self.project_root / self.whisper_binary

    @property
    def model_path_abs(self) -> Path:
        return self.project_root / self.model_path

    model_config = {"env_prefix": "JARVIS_STT_"}


settings = STTSettings()