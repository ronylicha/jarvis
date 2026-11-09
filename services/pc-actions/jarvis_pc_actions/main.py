"""Jarvis PC Actions FastAPI application."""

import hmac
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from jarvis_pc_actions.actions import (
    activate_window,
    get_clipboard,
    get_system_info,
    list_windows,
    send_notification,
    set_clipboard,
    take_screenshot,
)
from jarvis_pc_actions.config import settings

logger = structlog.get_logger(__name__)


# --- Auth ---

async def verify_token(x_jarvis_token: str = Header(default="")) -> str:
    """Verify bearer token. Disabled if JARVIS_PC_ACTIONS_API_TOKEN unset."""
    expected = os.environ.get("JARVIS_PC_ACTIONS_API_TOKEN")
    if expected is None:
        return "__anonymous__"
    if not x_jarvis_token or not hmac.compare_digest(x_jarvis_token, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing token")
    return "__authenticated__"


@asynccontextmanager
async def lifespan(app: FastAPI):
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logger.level),
    )
    logger.info("pc_actions.startup", port=settings.port)
    yield
    logger.info("pc_actions.shutdown")


app = FastAPI(title="Jarvis PC Actions", version="0.1.0", lifespan=lifespan)


# --- Models ---

class NotifyRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    urgency: str = Field(default="normal", pattern="^(low|normal|critical)$")


class ClipboardSetRequest(BaseModel):
    text: str = Field(..., min_length=1)


class ActivateWindowRequest(BaseModel):
    window_id: str = Field(..., min_length=1)


class ScreenshotRequest(BaseModel):
    region: list[int] | None = Field(default=None, description="[x, y, width, height]")


# --- Endpoints ---

@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "service": "jarvis-pc-actions",
        "version": "0.1.0",
    }


@app.post("/screenshot", dependencies=[Depends(verify_token)])
async def screenshot(request: ScreenshotRequest | None = None):
    """Capture the screen or a region. Returns base64-encoded PNG."""
    region = None
    if request and request.region and len(request.region) == 4:
        region = tuple(request.region)  # type: ignore

    try:
        result = await take_screenshot(region=region)
        return {
            "image_base64": result.image_base64,
            "width": result.width,
            "height": result.height,
            "format": result.format,
            "timestamp": result.timestamp,
        }
    except Exception as exc:
        logger.error("pc.screenshot_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Screenshot failed")


@app.get("/clipboard", dependencies=[Depends(verify_token)])
async def clipboard_get():
    """Read text from the system clipboard."""
    try:
        text = await get_clipboard()
        return {"text": text, "length": len(text)}
    except Exception as exc:
        logger.error("pc.clipboard_read_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Clipboard read failed")


@app.post("/clipboard", dependencies=[Depends(verify_token)])
async def clipboard_set(request: ClipboardSetRequest):
    """Write text to the system clipboard."""
    try:
        success = await set_clipboard(request.text)
        return {"success": success, "length": len(request.text)}
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except Exception as exc:
        logger.error("pc.clipboard_write_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Clipboard write failed")


@app.post("/notify", dependencies=[Depends(verify_token)])
async def notify(request: NotifyRequest):
    """Send a desktop notification."""
    success = await send_notification(request.title, request.body, request.urgency)
    return {"success": success}


@app.get("/windows", dependencies=[Depends(verify_token)])
async def windows_list():
    """List all visible windows."""
    windows = await list_windows()
    return {
        "windows": [
            {
                "id": w.window_id,
                "title": w.title,
                "is_active": w.is_active,
            }
            for w in windows
        ],
        "count": len(windows),
    }


@app.post("/windows/activate", dependencies=[Depends(verify_token)])
async def windows_activate(request: ActivateWindowRequest):
    """Bring a window to focus by its window ID."""
    success = await activate_window(request.window_id)
    if not success:
        raise HTTPException(status_code=404, detail="Window not found or activation failed")
    return {"success": True, "window_id": request.window_id}


@app.get("/system-info", dependencies=[Depends(verify_token)])
async def system_info():
    """Get basic system information (uptime, disk, memory, active window)."""
    info = await get_system_info()
    return info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)