"""Dual storage backend: SQLite (structured facts) + ChromaDB (semantic search)."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
import chromadb
import structlog
from chromadb.config import Settings as ChromaSettings

from jarvis_memory.config import settings

logger = structlog.get_logger(__name__)

# Schema for structured memories table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_agent ON memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
"""


class MemoryStore:
    """Unified memory store with SQLite persistence and ChromaDB vector search."""

    def __init__(self) -> None:
        self._chroma_client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        self._db_path = settings.sqlite_path
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize SQLite immediately; defer ChromaDB to first use (lazy loading).

        ChromaDB + sentence-transformers consume ~500 MB RAM and add ~5s startup.
        By deferring initialization, the memory service starts instantly and only
        loads the embedding model when recall() or remember() is first called.
        """
        # SQLite — lightweight, always ready
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.executescript(CREATE_TABLE_SQL)
            await db.commit()
        logger.info("memory.sqlite_ready", path=str(self._db_path))

        # ChromaDB deferred — will be initialized on first vector operation
        self._chroma_initialized = False
        self._initialized = True
        logger.info("memory.chroma_deferred", reason="lazy_loading")

    async def _ensure_chroma(self) -> None:
        """Lazy-initialize ChromaDB on first vector operation."""
        if self._chroma_initialized:
            return
        logger.info("memory.chroma_loading", reason="first_vector_operation")
        self._chroma_client = chromadb.PersistentClient(
            path=str(settings.data_dir_abs / "chromadb"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._chroma_client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        self._chroma_initialized = True
        logger.info(
            "memory.chroma_ready",
            collection=settings.chroma_collection,
            count=self._collection.count(),
        )

    async def remember(
        self,
        agent_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        memory_id: str | None = None,
    ) -> str:
        """Store a memory in both SQLite and ChromaDB.

        Returns the memory ID.
        """
        if not self._initialized:
            raise RuntimeError("MemoryStore not initialized. Call initialize() first.")

        mid = memory_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        tags_json = json.dumps(tags or [], ensure_ascii=False)

        # SQLite insert
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute(
                """INSERT INTO memories (id, agent_id, content, metadata, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (mid, agent_id, content, meta_json, tags_json, now, now),
            )
            await db.commit()

        # ChromaDB upsert — lazy-initialize on first vector operation
        await self._ensure_chroma()
        self._collection.upsert(
            ids=[mid],
            documents=[content],
            metadatas=[{
                "agent_id": agent_id,
                "tags": ",".join(tags or []),
                "created_at": now,
                **(metadata or {}),
            }],
        )

        logger.info("memory.stored", id=mid, agent=agent_id, chars=len(content))
        return mid

    async def recall(
        self,
        query: str,
        *,
        agent_id: str | None = None,
        limit: int | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across memories using ChromaDB embeddings."""
        if not self._initialized:
            raise RuntimeError("MemoryStore not initialized.")

        # Lazy-initialize ChromaDB on first vector operation
        await self._ensure_chroma()

        n_results = min(limit or settings.default_recall_limit, settings.max_recall_results)

        where_filter: dict[str, Any] | None = None
        if agent_id and tags:
            where_filter = {"$and": [{"agent_id": agent_id}, {"tags": {"$contains": ",".join(tags)}}]}
        elif agent_id:
            where_filter = {"agent_id": agent_id}
        elif tags:
            where_filter = {"tags": {"$contains": ",".join(tags)}}

        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        if results["ids"] and results["ids"][0]:
            for i, mid in enumerate(results["ids"][0]):
                memories.append({
                    "id": mid,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
                })

        logger.info("memory.recalled", query_chars=len(query), results=len(memories))
        return memories

    async def get(self, memory_id: str) -> dict[str, Any] | None:
        """Get a single memory by ID from SQLite."""
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "agent_id": row["agent_id"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]),
                "tags": json.loads(row["tags"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    async def forget(self, memory_id: str) -> bool:
        """Delete a memory from both SQLite and ChromaDB."""
        # SQLite delete
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await db.commit()
            deleted_sqlite = cursor.rowcount > 0

        # ChromaDB delete (ignore if not found)
        try:
            self._collection.delete(ids=[memory_id])
        except Exception:
            pass

        logger.info("memory.forgotten", id=memory_id, existed=deleted_sqlite)
        return deleted_sqlite

    async def list_agents(self) -> list[str]:
        """List all agent IDs that have stored memories."""
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute(
                "SELECT DISTINCT agent_id FROM memories ORDER BY agent_id"
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def stats(self) -> dict[str, Any]:
        """Return memory store statistics."""
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM memories")
            total = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(DISTINCT agent_id) FROM memories")
            agents = (await cursor.fetchone())[0]

        chroma_count = self._collection.count() if self._collection else 0

        return {
            "total_memories": total,
            "chroma_vectors": chroma_count,
            "unique_agents": agents,
            "db_size_mb": round(self._db_path.stat().st_size / 1024 / 1024, 2)
            if self._db_path.exists()
            else 0,
        }