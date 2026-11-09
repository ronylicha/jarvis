"""Jarvis Memory FastAPI application."""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from jarvis_memory.config import settings
from jarvis_memory.store import MemoryStore

logger = structlog.get_logger(__name__)

store = MemoryStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logger.level),
    )
    logger.info("memory.startup", port=settings.port)
    await store.initialize()
    yield
    logger.info("memory.shutdown")


app = FastAPI(title="Jarvis Memory", version="0.1.0", lifespan=lifespan)


# --- Request/Response models ---


class RememberRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=10000)
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None
    memory_id: str | None = None


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    agent_id: str | None = None
    limit: int = Field(default=5, ge=1, le=20)
    tags: list[str] | None = None


# --- Endpoints ---


@app.get("/health")
async def health():
    """Health check with store status."""
    try:
        s = await store.stats()
        return {"status": "ok", **s, "service": "jarvis-memory", "version": "0.1.0"}
    except Exception as exc:
        logger.error("memory.health_error", error=str(exc))
        return {"status": "error", "service": "jarvis-memory", "version": "0.1.0"}


@app.post("/remember")
async def remember(request: RememberRequest):
    """Store a new memory. Returns the memory ID."""
    try:
        mid = await store.remember(
            agent_id=request.agent_id,
            content=request.content,
            metadata=request.metadata,
            tags=request.tags,
            memory_id=request.memory_id,
        )
        return {"id": mid, "status": "stored"}
    except Exception as exc:
        logger.error("memory.remember_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to store memory.")


@app.post("/recall")
async def recall(request: RecallRequest):
    """Semantic search across memories."""
    try:
        results = await store.recall(
            query=request.query,
            agent_id=request.agent_id,
            limit=request.limit,
            tags=request.tags,
        )
        return {"results": results, "count": len(results)}
    except Exception as exc:
        logger.error("memory.recall_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Memory search failed.")


@app.get("/memories/{memory_id}")
async def get_memory(memory_id: str):
    """Get a single memory by ID."""
    result = await store.get(memory_id)
    if not result:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return result


@app.delete("/memories/{memory_id}")
async def forget(memory_id: str):
    """Delete a memory."""
    deleted = await store.forget(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"id": memory_id, "status": "forgotten"}


@app.get("/agents")
async def list_agents():
    """List all agent IDs with stored memories."""
    agents = await store.list_agents()
    return {"agents": agents}


@app.get("/stats")
async def stats():
    """Memory store statistics."""
    return await store.stats()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)