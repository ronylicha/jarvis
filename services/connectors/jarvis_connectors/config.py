"""Configuration for Jarvis Connectors service."""

from pathlib import Path

from pydantic_settings import BaseSettings


class ConnectorsSettings(BaseSettings):
    """Connectors service configuration."""

    project_root: Path = Path.home() / "projects" / "jarvis"
    credentials_dir: Path = Path("data/connectors")

    host: str = "0.0.0.0"
    port: int = 8005

    # Shell safety
    allowed_shell_commands: list[str] = [
        "ls", "cat", "head", "tail", "wc", "find", "grep",
        "git status", "git log", "git diff", "git branch",
        "docker ps", "docker images",
        "df -h", "free -h", "uptime",
    ]
    shell_timeout_seconds: int = 30

    # Filesystem
    allowed_fs_roots: list[str] = [
        str(Path.home() / "Documents"),
        str(Path.home() / "Projects"),
        str(Path.home() / "Desktop"),
    ]

    model_config = {"env_prefix": "JARVIS_CONNECTORS_"}


settings = ConnectorsSettings()