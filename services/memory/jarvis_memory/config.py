"""Configuration for Jarvis Memory service."""

from pathlib import Path

from pydantic_settings import BaseSettings


class MemorySettings(BaseSettings):
    """Memory service configuration loaded from environment / .env."""

    project_root: Path = Path.home() / "projects" / "jarvis"
    data_dir: Path = Path("data/memory")

    host: str = "0.0.0.0"
    port: int = 8004

    # ChromaDB
    chroma_collection: str = "jarvis_memories"
    embedding_model: str = "all-MiniLM-L6-v2"  # ~90 MB, fast, good multilingual

    # SQLite
    sqlite_db: str = "memories.db"

    # Limits
    max_recall_results: int = 20
    default_recall_limit: int = 5

    @property
    def data_dir_abs(self) -> Path:
        path = self.project_root / self.data_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir_abs / self.sqlite_db

    model_config = {"env_prefix": "JARVIS_MEMORY_"}


settings = MemorySettings()