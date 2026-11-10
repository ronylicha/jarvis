import logging
"""Jarvis Memory FastAPI application."""

import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from jarvis_memory.config import settings
from jarvis_memory.store import MemoryStore

logger = structlog.get_logger(__name__)

store = MemoryStore()

# --- Auth ---

def _expected_token() -> str | None:
    """Return the expected API token from env, or None if auth disabled."""
    token = os.environ.get("JARVIS_MEMORY_API_TOKEN")
    return token if token else None


async def verify_token(x_jarvis_token: str = Header(default="")) -> str:
    """Verify the bearer token. If JARVIS_MEMORY_API_TOKEN is unset, auth is disabled."""
    expected = _expected_token()
    if expected is None:
        return "__anonymous__"  # auth disabled (local dev)
    if not x_jarvis_token:
        raise HTTPException(status_code=401, detail="Missing X-Jarvis-Token header")
    if not hmac.compare_digest(x_jarvis_token, expected):
        raise HTTPException(status_code=403, detail="Invalid token")
    return "__authenticated__"


async def verify_admin(x_jarvis_token: str = Header(default="")) -> str:
    """Admin-level access — requires token when configured."""
    expected = _expected_token()
    if expected is None:
        return "__admin__"
    if not x_jarvis_token or not hmac.compare_digest(x_jarvis_token, expected):
        raise HTTPException(status_code=403, detail="Admin access required")
    return "__admin__"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    auth_mode = "disabled" if _expected_token() is None else "enabled"
    logger.info("memory.startup", port=settings.port, auth=auth_mode)
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
    """Health check with store status — no auth required."""
    try:
        s = await store.stats()
        return {"status": "ok", **s, "service": "jarvis-memory", "version": "0.1.0"}
    except Exception as exc:
        logger.error("memory.health_error", error=str(exc))
        return {"status": "error", "service": "jarvis-memory", "version": "0.1.0"}


@app.post("/remember", dependencies=[Depends(verify_token)])
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


@app.post("/recall", dependencies=[Depends(verify_token)])
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


@app.get("/memories/{memory_id}", dependencies=[Depends(verify_token)])
async def get_memory(memory_id: str):
    """Get a single memory by ID."""
    result = await store.get(memory_id)
    if not result:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return result


@app.delete("/memories/{memory_id}", dependencies=[Depends(verify_token)])
async def forget(memory_id: str):
    """Delete a memory. Requires authentication."""
    deleted = await store.forget(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"id": memory_id, "status": "forgotten"}


@app.get("/agents", dependencies=[Depends(verify_admin)])
async def list_agents():
    """List all agent IDs with stored memories. Admin-only."""
    agents = await store.list_agents()
    return {"agents": agents}


@app.get("/stats", dependencies=[Depends(verify_admin)])
async def stats():
    """Memory store statistics. Admin-only."""
    return await store.stats()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)