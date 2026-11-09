"""Configuration for Jarvis PC Actions service."""

from pathlib import Path

from pydantic_settings import BaseSettings


class PCActionsSettings(BaseSettings):
    """PC Actions service configuration."""

    host: str = "0.0.0.0"
    port: int = 8006

    # Screenshot
    screenshot_dir: Path = Path.home() / "projects" / "jarvis" / "data" / "screenshots"
    max_screenshot_size_mb: int = 10

    # Notifications
    notification_timeout_seconds: int = 5

    # Clipboard
    max_clipboard_size_bytes: int = 1_000_000  # 1 MB

    model_config = {"env_prefix": "JARVIS_PC_ACTIONS_"}


settings = PCActionsSettings()