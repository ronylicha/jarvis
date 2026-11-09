"""Configuration for Jarvis TTS service."""

from pathlib import Path

from pydantic_settings import BaseSettings


class TTSSettings(BaseSettings):
    """TTS service configuration loaded from environment / .env."""

    project_root: Path = Path.home() / "projects" / "jarvis"
    piper_binary: Path = Path("bin/piper/piper")
    voices_dir: Path = Path("models")
    default_voice: str = "fr_FR-siwis-medium"

    host: str = "0.0.0.0"
    port: int = 8002

    default_speed: float = 1.0
    min_speed: float = 0.5
    max_speed: float = 2.0
    timeout_seconds: int = 30
    max_text_length: int = 5000

    @property
    def piper_binary_abs(self) -> Path:
        return self.project_root / self.piper_binary

    @property
    def voices_dir_abs(self) -> Path:
        return self.project_root / self.voices_dir

    model_config = {"env_prefix": "JARVIS_TTS_"}


settings = TTSSettings()