"""Real-time scanner for active agent sessions (Claude, Codex, Kimi, ZAI)."""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
import structlog

from jarvis_agent_sessions.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class AgentSession:
    """Represents an active or recent agent session."""

    agent_type: str  # claude, codex, kimi, zai
    session_id: str
    status: str  # active, idle, stopped
    pid: int | None = None
    project_path: str | None = None
    model: str | None = None
    last_activity: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    proxy_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _find_claude_processes() -> list[dict[str, Any]]:
    """Find running Claude Code processes and extract session info."""
    sessions = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline)
            if "claude" not in cmdline_str.lower():
                continue
            # Skip non-agent processes that happen to contain "claude" in their path/name
            if any(skip in cmdline_str for skip in [
                "grep", "wrap-", "setup-boot", "earlyoom",
                "chrome-native-host", "claudenest-agent", "chrome-extension",
                "notebooklm-mcp", "developer-kit-tools",
            ]):
                continue
            # Must be an actual claude CLI process (binary named "claude" in argv[0])
            if cmdline and "claude" not in cmdline[0].lower().split("/")[-1]:
                continue

            pid = proc.info["pid"]
            create_time = proc.info.get("create_time")
            started_at = (
                datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat()
                if create_time
                else None
            )

            # Try to find the associated session JSONL file
            session_file = None
            sessions_dir = settings.claude_sessions_dir
            if sessions_dir.exists():
                # Find most recently modified JSONL in -home-rony project dir
                home_project = sessions_dir / "-home-rony"
                if home_project.exists():
                    jsonls = sorted(
                        home_project.glob("*.jsonl"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if jsonls:
                        session_file = str(jsonls[0])

            sessions.append({
                "agent_type": "claude",
                "session_id": f"claude-{pid}",
                "status": "active",
                "pid": pid,
                "started_at": started_at,
                "session_file": session_file,
                "model": _extract_model_from_cmdline(cmdline),
                "proxy_url": _detect_proxy_url(cmdline),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sessions


def _find_codex_processes() -> list[dict[str, Any]]:
    """Find running Codex CLI processes."""
    sessions = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline)
            if "codex" not in cmdline_str.lower():
                continue
            if any(skip in cmdline_str for skip in ["grep", "extension-host", "chrome"]):
                continue

            pid = proc.info["pid"]
            create_time = proc.info.get("create_time")
            started_at = (
                datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat()
                if create_time
                else None
            )

            sessions.append({
                "agent_type": "codex",
                "session_id": f"codex-{pid}",
                "status": "active",
                "pid": pid,
                "started_at": started_at,
                "model": _extract_codex_model(),
                "proxy_url": settings.usage_shim_url,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sessions


def _find_kimi_processes() -> list[dict[str, Any]]:
    """Find running Kimi CLI processes."""
    sessions = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline)
            if "kimi" not in cmdline_str.lower():
                continue
            if "grep" in cmdline_str:
                continue

            pid = proc.info["pid"]
            create_time = proc.info.get("create_time")
            started_at = (
                datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat()
                if create_time
                else None
            )

            sessions.append({
                "agent_type": "kimi",
                "session_id": f"kimi-{pid}",
                "status": "active",
                "pid": pid,
                "started_at": started_at,
                "model": _extract_kimi_model(),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sessions


def _find_zai_processes() -> list[dict[str, Any]]:
    """Find running ZAI MCP server processes."""
    sessions = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline)
            if "zai" not in cmdline_str.lower():
                continue
            if "grep" in cmdline_str:
                continue

            pid = proc.info["pid"]
            create_time = proc.info.get("create_time")
            started_at = (
                datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat()
                if create_time
                else None
            )

            # Check latest ZAI log for activity
            log_files = sorted(
                settings.zai_logs_dir.glob("zai-mcp-*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            latest_log = str(log_files[0]) if log_files else None

            sessions.append({
                "agent_type": "zai",
                "session_id": f"zai-{pid}",
                "status": "active",
                "pid": pid,
                "started_at": started_at,
                "latest_log": latest_log,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sessions


def _find_ghostcli_relay() -> dict[str, Any] | None:
    """Detect if the ghostcli usage-shim relay is running."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline)
            if "usage-shim" in cmdline_str and "--serve" in cmdline_str:
                return {
                    "pid": proc.info["pid"],
                    "url": settings.usage_shim_url,
                    "upstream": settings.ghostcli_base_url,
                    "status": "active",
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _extract_model_from_cmdline(cmdline: list[str]) -> str | None:
    """Extract model name from Claude CLI command line."""
    for i, arg in enumerate(cmdline):
        if arg == "--model" and i + 1 < len(cmdline):
            return cmdline[i + 1]
    # Check env var
    return os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CC2_MODEL")


def _extract_codex_model() -> str | None:
    """Extract model from Codex config."""
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists():
        return None
    try:
        content = config_path.read_text()
        match = re.search(r'^model\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return match.group(1) if match else None
    except Exception:
        return None


def _extract_kimi_model() -> str | None:
    """Extract model from Kimi config."""
    if not settings.kimi_config_path.exists():
        return None
    try:
        content = settings.kimi_config_path.read_text()
        match = re.search(r'^default_model\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return match.group(1) if match else None
    except Exception:
        return None


def _detect_proxy_url(cmdline: list[str]) -> str | None:
    """Detect if a Claude process is using a proxy relay."""
    # Check if usage-shim is running (relay mode)
    relay = _find_ghostcli_relay()
    if relay:
        return relay["url"]
    # Check ANTHROPIC_BASE_URL env
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    if base_url and base_url != "https://api.anthropic.com":
        return base_url
    return None


def scan_all_sessions() -> dict[str, Any]:
    """Scan all agent types and return consolidated session data."""
    claude_sessions = _find_claude_processes()
    codex_sessions = _find_codex_processes()
    kimi_sessions = _find_kimi_processes()
    zai_sessions = _find_zai_processes()
    relay = _find_ghostcli_relay()

    all_sessions = claude_sessions + codex_sessions + kimi_sessions + zai_sessions

    return {
        "sessions": all_sessions,
        "total_active": len(all_sessions),
        "by_agent": {
            "claude": len(claude_sessions),
            "codex": len(codex_sessions),
            "kimi": len(kimi_sessions),
            "zai": len(zai_sessions),
        },
        "proxy_relay": relay,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }