"""Configuration for Jarvis Core service."""

from pydantic_settings import BaseSettings


class CoreSettings(BaseSettings):
    """Core service configuration loaded from environment / .env."""

    host: str = "0.0.0.0"
    port: int = 8003

    # Provider API keys (optional — only set what you use)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    moonshot_api_key: str = ""
    minimax_api_key: str = ""
    zhipu_api_key: str = ""
    openrouter_api_key: str = ""

    # Ollama (local fallback, installed later per user decision)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-q4_K_M"

    # Default provider when none specified
    default_provider: str = "anthropic"

    # Timeouts
    request_timeout_seconds: int = 60

    model_config = {"env_prefix": "JARVIS_CORE_"}


settings = CoreSettings()