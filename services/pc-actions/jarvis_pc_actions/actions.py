"""PC action primitives — screen capture, clipboard, notifications, window control.

All functions are Linux/X11-first with graceful fallbacks.
"""

import asyncio
import base64
import subprocess
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import structlog

from jarvis_pc_actions.config import settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ScreenshotResult:
    """Result of a screen capture."""
    image_base64: str
    width: int
    height: int
    format: str = "png"
    timestamp: float = 0.0


@dataclass(frozen=True)
class WindowInfo:
    """Information about a desktop window."""
    window_id: str
    title: str
    app_name: str
    is_active: bool


# --- Screenshot ---

async def take_screenshot(region: tuple[int, int, int, int] | None = None) -> ScreenshotResult:
    """Capture the screen or a region using scrot/import/Pillow.

    Args:
        region: Optional (x, y, width, height) crop region.

    Returns:
        ScreenshotResult with base64-encoded PNG.
    """
    settings.screenshot_dir.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=region)
    except Exception:
        # Fallback to scrot (Linux)
        tmp_path = settings.screenshot_dir / f"_tmp_{int(time.time())}.png"
        cmd = ["scrot", "-o", str(tmp_path)]
        if region:
            x, y, w, h = region
            cmd = ["scrot", "-o", "-a", f"{x},{y},{w},{h}", str(tmp_path)]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        if not tmp_path.exists():
            raise RuntimeError("Screenshot capture failed — install scrot or Pillow")

        from PIL import Image
        img = Image.open(tmp_path)
        tmp_path.unlink(missing_ok=True)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode()

    logger.info("pc.screenshot", width=img.width, height=img.height)
    return ScreenshotResult(
        image_base64=b64,
        width=img.width,
        height=img.height,
        timestamp=time.time(),
    )


# --- Clipboard ---

async def get_clipboard() -> str:
    """Read text from the system clipboard."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "xclip", "-selection", "clipboard", "-o",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        text = stdout.decode(errors="replace")
        if len(text.encode()) > settings.max_clipboard_size_bytes:
            return text[:settings.max_clipboard_size_bytes]
        return text
    except FileNotFoundError:
        # Fallback to xsel
        proc = await asyncio.create_subprocess_exec(
            "xsel", "--clipboard", "--output",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="replace")


async def set_clipboard(text: str) -> bool:
    """Write text to the system clipboard."""
    if len(text.encode()) > settings.max_clipboard_size_bytes:
        raise ValueError(f"Text exceeds {settings.max_clipboard_size_bytes} bytes limit")

    try:
        proc = await asyncio.create_subprocess_exec(
            "xclip", "-selection", "clipboard",
            stdin=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=text.encode())
        return proc.returncode == 0
    except FileNotFoundError:
        proc = await asyncio.create_subprocess_exec(
            "xsel", "--clipboard", "--input",
            stdin=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=text.encode())
        return proc.returncode == 0


# --- Notifications ---

async def send_notification(title: str, body: str, urgency: str = "normal") -> bool:
    """Send a desktop notification via notify-send.

    Args:
        title: Notification title.
        body: Notification body text.
        urgency: low, normal, or critical.
    """
    valid_urgencies = {"low", "normal", "critical"}
    if urgency not in valid_urgencies:
        urgency = "normal"

    try:
        proc = await asyncio.create_subprocess_exec(
            "notify-send",
            "-u", urgency,
            "-t", str(settings.notification_timeout_seconds * 1000),
            "-a", "Jarvis",
            title, body,
        )
        await proc.wait()
        logger.info("pc.notification", title=title, urgency=urgency)
        return proc.returncode == 0
    except FileNotFoundError:
        logger.warning("pc.notify_send_missing")
        return False


# --- Window Control ---

async def list_windows() -> list[WindowInfo]:
    """List all visible windows using wmctrl or xdotool."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "wmctrl", "-l", "-p",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode(errors="replace").strip().splitlines()

        # Get active window ID
        active_proc = await asyncio.create_subprocess_exec(
            "xdotool", "getactivewindow",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        active_stdout, _ = await active_proc.communicate()
        active_id = active_stdout.decode().strip()

        windows = []
        for line in lines:
            parts = line.split(None, 3)
            if len(parts) >= 4:
                wid = parts[0]
                title = parts[3] if len(parts) > 3 else ""
                windows.append(WindowInfo(
                    window_id=wid,
                    title=title,
                    app_name="",
                    is_active=(wid == active_id),
                ))
        return windows
    except FileNotFoundError:
        logger.warning("pc.wmctrl_missing")
        return []


async def activate_window(window_id: str) -> bool:
    """Bring a window to focus by its window ID."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "wmctrl", "-i", "-a", window_id,
        )
        await proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        # Fallback to xdotool
        try:
            proc = await asyncio.create_subprocess_exec(
                "xdotool", "windowactivate", window_id,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            logger.warning("pc.window_control_missing")
            return False


async def get_active_window_title() -> str:
    """Get the title of the currently active window."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "xdotool", "getactivewindow", "getwindowname",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="replace").strip()
    except FileNotFoundError:
        return ""


# --- System Info ---

async def get_system_info() -> dict:
    """Gather basic system information."""
    info: dict = {}

    # Uptime
    try:
        proc = await asyncio.create_subprocess_exec(
            "uptime", "-p",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        info["uptime"] = stdout.decode().strip()
    except Exception:
        pass

    # Disk usage
    try:
        proc = await asyncio.create_subprocess_exec(
            "df", "-h", "/",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode().strip().splitlines()
        if len(lines) >= 2:
            info["disk"] = lines[1].split()
    except Exception:
        pass

    # Memory
    try:
        proc = await asyncio.create_subprocess_exec(
            "free", "-h",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode().strip().splitlines()
        if len(lines) >= 2:
            info["memory"] = lines[1].split()
    except Exception:
        pass

    # Active window
    info["active_window"] = await get_active_window_title()

    return info