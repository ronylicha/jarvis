import logging
"""Jarvis Connectors FastAPI application."""

import asyncio
import re
import shlex
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from jarvis_connectors.config import settings

logger = structlog.get_logger(__name__)


# --- Auth (same pattern as memory-service) ---

async def verify_token(x_jarvis_token: str = Header(default="")) -> str:
    """Verify bearer token. Disabled if JARVIS_CONNECTORS_API_TOKEN unset."""
    import hmac
    import os
    expected = os.environ.get("JARVIS_CONNECTORS_API_TOKEN")
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
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    logger.info("connectors.startup", port=settings.port)
    yield
    logger.info("connectors.shutdown")


app = FastAPI(title="Jarvis Connectors", version="0.1.0", lifespan=lifespan)


# --- Models ---

class ShellRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=500)
    timeout: int = Field(default=30, ge=1, le=120)


class FileReadRequest(BaseModel):
    path: str = Field(..., min_length=1)
    max_lines: int = Field(default=100, ge=1, le=10000)


class GoogleCalendarRequest(BaseModel):
    max_results: int = Field(default=10, ge=1, le=100)
    time_min: str | None = None  # ISO 8601


# --- Shell-safe executor ---

_SHELL_METACHARACTERS = re.compile(r'[;|&$`\n\r(){}<>\\!]')


def _is_command_allowed(command: str) -> tuple[bool, list[str]]:
    """Check if a command is in the allowlist. Returns (allowed, parsed_parts).

    Rejects any command containing shell metacharacters to prevent parser
    differential attacks between shlex and /bin/sh. The caller MUST use
    create_subprocess_exec with the returned parts (never create_subprocess_shell).
    """
    if _SHELL_METACHARACTERS.search(command):
        return False, []

    try:
        parts = shlex.split(command)
    except ValueError:
        return False, []

    if not parts:
        return False, []

    base_cmd = parts[0]
    for allowed in settings.allowed_shell_commands:
        allowed_parts = shlex.split(allowed)
        if not allowed_parts:
            continue
        if parts[:len(allowed_parts)] == allowed_parts:
            return True, parts
        if base_cmd == allowed_parts[0] and len(allowed_parts) == 1:
            return True, parts
    return False, []


@app.post("/shell/exec", dependencies=[Depends(verify_token)])
async def shell_exec(request: ShellRequest):
    """Execute an allowed shell command safely.

    Uses create_subprocess_exec (not shell) to eliminate shell injection.
    Commands containing shell metacharacters (;|&$` etc.) are always rejected.
    """
    allowed, parsed_parts = _is_command_allowed(request.command)
    if not allowed:
        logger.warning("connectors.shell_rejected", command=request.command)
        raise HTTPException(
            status_code=403,
            detail="Command not in allowlist or contains forbidden characters.",
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            *parsed_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=request.timeout
        )
        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode(errors="replace")[:10000],
            "stderr": stderr.decode(errors="replace")[:5000],
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Command timed out")
    except Exception as exc:
        logger.error("connectors.shell_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Shell execution failed")


# --- Filesystem ---

def _validate_fs_path(path_str: str) -> Path:
    """Validate path is within allowed roots to prevent directory traversal."""
    resolved = Path(path_str).resolve()
    for root in settings.allowed_fs_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise HTTPException(
        status_code=403,
        detail=f"Path outside allowed directories: {settings.allowed_fs_roots}",
    )


@app.post("/fs/read", dependencies=[Depends(verify_token)])
async def fs_read(request: FileReadRequest):
    """Read file contents from allowed directories only."""
    safe_path = _validate_fs_path(request.path)

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not safe_path.is_file():
        raise HTTPException(status_code=400, detail="Not a regular file")

    try:
        # Stream-read to avoid loading entire file into memory for large files
        import itertools
        with open(safe_path, errors="replace") as f:
            lines = list(itertools.islice(f, request.max_lines))
        # Count total lines without loading full file (bounded scan)
        with open(safe_path, errors="replace") as f:
            total_lines = sum(1 for _ in f)
        return {
            "path": str(safe_path),
            "lines": [line.rstrip("\n") for line in lines],
            "total_lines": total_lines,
            "truncated": len(lines) < total_lines,
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as exc:
        logger.error("connectors.fs_read_error", error=str(exc))
        raise HTTPException(status_code=500, detail="File read failed")


@app.get("/fs/list", dependencies=[Depends(verify_token)])
async def fs_list(path: str = "/", max_items: int = 50):
    """List directory contents within allowed roots."""
    safe_path = _validate_fs_path(path)

    if not safe_path.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    try:
        entries = []
        for i, entry in enumerate(sorted(safe_path.iterdir())):
            if i >= max_items:
                break
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return {"path": str(safe_path), "entries": entries}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


# --- Google Workspace (stub — requires OAuth2 setup) ---

@app.get("/google/calendar", dependencies=[Depends(verify_token)])
async def google_calendar(max_results: int = Field(default=10, ge=1, le=100)):
    """List upcoming Google Calendar events.

    Requires OAuth2 credentials in data/connectors/google-credentials.json.
    Run scripts/setup_google_oauth.sh first.
    """
    creds_path = settings.project_root / settings.credentials_dir / "google-credentials.json"
    token_path = settings.project_root / settings.credentials_dir / "google-token.json"

    if not creds_path.exists():
        return {
            "status": "not_configured",
            "message": "Google OAuth2 not set up. Run scripts/setup_google_oauth.sh",
        }

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path))

        if not creds or not creds.valid:
            return {
                "status": "auth_required",
                "message": "Token expired or invalid. Re-run OAuth2 flow.",
            }

        service = build("calendar", "v3", credentials=creds)
        events = service.events().list(
            calendarId="primary",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        items = events.get("items", [])
        return {
            "status": "ok",
            "events": [
                {
                    "summary": e.get("summary", ""),
                    "start": e.get("start", {}).get("dateTime", ""),
                    "end": e.get("end", {}).get("dateTime", ""),
                }
                for e in items
            ],
        }
    except ImportError:
        return {"status": "missing_deps", "message": "google-api-python-client not installed"}
    except Exception as exc:
        logger.error("connectors.google_calendar_error", error=str(exc))
        return {"status": "error", "message": "Calendar fetch failed"}


@app.get("/health")
async def health():
    """Health check with connector status."""
    creds_exists = (
        settings.project_root / settings.credentials_dir / "google-credentials.json"
    ).exists()
    return {
        "status": "ok",
        "google_configured": creds_exists,
        "shell_allowlist_size": len(settings.allowed_shell_commands),
        "fs_roots": settings.allowed_fs_roots,
        "service": "jarvis-connectors",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)