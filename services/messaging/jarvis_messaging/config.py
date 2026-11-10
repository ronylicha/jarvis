"""Configuration for Jarvis Messaging service."""

from pathlib import Path

from pydantic_settings import BaseSettings


class MessagingSettings(BaseSettings):
    """Messaging service configuration loaded from environment / .env."""

    host: str = "127.0.0.1"
    port: int = 8008

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_poll_interval: int = 5  # seconds

    # WhatsApp Business API
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_version: str = "v21.0"
    whatsapp_base_url: str = "https://graph.facebook.com"

    # Email IMAP/SMTP
    email_imap_host: str = ""
    email_imap_port: int = 993
    email_imap_user: str = ""
    email_imap_pass: str = ""
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_pass: str = ""
    email_check_interval: int = 60  # seconds
    email_max_fetch: int = 20

    # Data
    data_dir: Path = Path.home() / "projects" / "jarvis" / "data" / "messaging"

    model_config = {"env_prefix": "JARVIS_MESSAGING_"}


settings = MessagingSettings()