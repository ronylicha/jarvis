"""Configuration for Jarvis Agent Sessions service."""

from pathlib import Path

from pydantic_settings import BaseSettings


class AgentSessionsSettings(BaseSettings):
    """Agent sessions service configuration."""

    host: str = "0.0.0.0"
    port: int = 8007

    # GhostCLI proxy relay (token counting passes through this)
    ghostcli_base_url: str = "https://ghostcli.cloud"
    ghostcli_api_key: str = ""
    usage_shim_url: str = "http://127.0.0.1:4748"

    # Session scan paths
    claude_sessions_dir: Path = Path.home() / ".claude" / "projects"
    codex_sessions_dir: Path = Path.home() / ".codex" / "sessions"
    kimi_config_path: Path = Path.home() / ".kimi" / "config.toml"
    zai_logs_dir: Path = Path.home() / ".zai"

    # Scan interval for SSE polling
    scan_interval_seconds: float = 5.0

    model_config = {"env_prefix": "JARVIS_AGENT_SESSIONS_"}


settings = AgentSessionsSettings()