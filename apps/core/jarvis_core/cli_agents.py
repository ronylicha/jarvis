"""CLI Agent Detector — reads existing auth from installed CLI tools.

Instead of implementing OAuth flows, Jarvis detects which CLI agents are
installed and authenticated on the system by reading their native config files:

- Claude Code: ~/.claude/.credentials.json (OAuth tokens)
- Codex CLI:   ~/.codex/auth.json (API key or OAuth tokens)
- Kimi Code:   ~/.kimi-code/credentials/*.json (OAuth tokens)
- cc2/cc2f:    ~/.config/cc2/env (ghostcli proxy API key)
- ZAI:         ~/.zai/zai-mcp-*.log (MCP server)

This module provides:
- Detection of installed/authenticated CLI agents
- Session discovery (active conversations per agent)
- Model info extraction from CLI configs
- No OAuth flow implementation needed — CLIs handle their own auth
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

HOME = Path.home()


@dataclass
class CLIAgentInfo:
    """Information about a detected CLI agent."""

    name: str
    cli_command: str
    auth_type: str  # "oauth", "api_key", "proxy", "none"
    is_installed: bool = False
    is_authenticated: bool = False
    model: str | None = None
    config_path: str | None = None
    session_count: int = 0
    latest_session: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _read_json_safe(path: Path) -> dict | list | None:
    """Read and parse a JSON file, returning None on any error."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a shell env file (KEY=VALUE lines) into a dict."""
    result: dict[str, str] = {}
    try:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        pass
    return result


# --- Per-agent detectors ---


def detect_claude() -> CLIAgentInfo:
    """Detect Claude Code CLI installation and auth status."""
    info = CLIAgentInfo(
        name="Claude Code",
        cli_command="claude",
        auth_type="oauth",
        config_path=str(HOME / ".claude"),
    )

    # Check if CLI is installed
    import shutil
    info.is_installed = shutil.which("claude") is not None

    if not info.is_installed:
        return info

    # Check credentials
    creds_path = HOME / ".claude" / ".credentials.json"
    creds = _read_json_safe(creds_path)
    if creds and isinstance(creds, dict):
        # Claude stores OAuth tokens under 'claudeAiOauth' key
        oauth_data = creds.get("claudeAiOauth")
        if oauth_data and isinstance(oauth_data, dict):
            info.is_authenticated = True
            info.metadata["has_oauth"] = True
            info.metadata["oauth_keys"] = list(oauth_data.keys())[:5]

    # Count sessions
    projects_dir = HOME / ".claude" / "projects"
    if projects_dir.exists():
        # Find -home-rony project dir
        for d in projects_dir.iterdir():
            if d.is_dir() and "home-rony" in d.name:
                jsonls = list(d.glob("*.jsonl"))
                info.session_count = len(jsonls)
                if jsonls:
                    latest = max(jsonls, key=lambda p: p.stat().st_mtime)
                    info.latest_session = str(latest)
                    mtime = datetime.fromtimestamp(
                        latest.stat().st_mtime, tz=timezone.utc
                    )
                    info.metadata["latest_session_age_hours"] = round(
                        (datetime.now(timezone.utc) - mtime).total_seconds() / 3600, 1
                    )
                break

    # Extract model from settings
    settings_path = HOME / ".claude" / "settings.json"
    settings = _read_json_safe(settings_path)
    if settings and isinstance(settings, dict):
        info.model = settings.get("model")

    logger.info(
        "cli_agent.detected",
        agent="claude",
        installed=info.is_installed,
        authenticated=info.is_authenticated,
        sessions=info.session_count,
    )
    return info


def detect_codex() -> CLIAgentInfo:
    """Detect Codex CLI installation and auth status."""
    info = CLIAgentInfo(
        name="Codex (OpenAI)",
        cli_command="codex",
        auth_type="api_key",
        config_path=str(HOME / ".codex"),
    )

    import shutil
    info.is_installed = shutil.which("codex") is not None

    if not info.is_installed:
        return info

    # Check auth
    auth_path = HOME / ".codex" / "auth.json"
    auth = _read_json_safe(auth_path)
    if auth and isinstance(auth, dict):
        info.auth_type = auth.get("auth_mode", "api_key")
        if auth.get("OPENAI_API_KEY") or auth.get("tokens"):
            info.is_authenticated = True
            info.metadata["auth_mode"] = auth.get("auth_mode")

    # Extract model from config.toml
    config_path = HOME / ".codex" / "config.toml"
    if config_path.exists():
        try:
            content = config_path.read_text(encoding="utf-8")
            match = re.search(r'^model\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                info.model = match.group(1)
            # Check for ghostcli provider
            if "ghostcli" in content.lower():
                info.metadata["provider"] = "ghostcli"
                info.auth_type = "proxy"
        except Exception:
            pass

    # Count sessions
    sessions_dir = HOME / ".codex" / "sessions"
    if sessions_dir.exists():
        count = 0
        latest_mtime = 0.0
        latest_path = ""
        for root, dirs, files in os.walk(sessions_dir):
            for f in files:
                fp = os.path.join(root, f)
                count += 1
                mt = os.path.getmtime(fp)
                if mt > latest_mtime:
                    latest_mtime = mt
                    latest_path = fp
        info.session_count = count
        if latest_path:
            info.latest_session = latest_path

    logger.info(
        "cli_agent.detected",
        agent="codex",
        installed=info.is_installed,
        authenticated=info.is_authenticated,
        model=info.model,
    )
    return info


def detect_kimi() -> CLIAgentInfo:
    """Detect Kimi Code CLI installation and auth status."""
    info = CLIAgentInfo(
        name="Kimi Code",
        cli_command="kimi",
        auth_type="oauth",
        config_path=str(HOME / ".kimi-code"),
    )

    import shutil
    kimi_bin = HOME / ".kimi-code" / "bin" / "kimi"
    info.is_installed = shutil.which("kimi") is not None or kimi_bin.exists()

    if not info.is_installed:
        return info

    # Check credentials
    creds_dir = HOME / ".kimi-code" / "credentials"
    if creds_dir.exists():
        cred_files = list(creds_dir.glob("*.json"))
        if cred_files:
            info.is_authenticated = True
            info.metadata["credential_files"] = [f.name for f in cred_files]

    # Extract model from config.toml
    config_path = HOME / ".kimi-code" / "config.toml"
    if config_path.exists():
        try:
            content = config_path.read_text(encoding="utf-8")
            match = re.search(r'^default_model\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                info.model = match.group(1)
        except Exception:
            pass

    logger.info(
        "cli_agent.detected",
        agent="kimi",
        installed=info.is_installed,
        authenticated=info.is_authenticated,
        model=info.model,
    )
    return info


def detect_cc2() -> CLIAgentInfo:
    """Detect cc2/cc2f (ghostcli proxy wrapper) installation and auth."""
    info = CLIAgentInfo(
        name="cc2 (GhostCLI Proxy)",
        cli_command="cc2",
        auth_type="proxy",
        config_path=str(HOME / ".config" / "cc2"),
    )

    import shutil
    info.is_installed = shutil.which("cc2") is not None

    if not info.is_installed:
        return info

    # Read env file for proxy config
    env_path = HOME / ".config" / "cc2" / "env"
    env_vars = _read_env_file(env_path)

    if env_vars.get("ANTHROPIC_API_KEY"):
        info.is_authenticated = True
        info.metadata["base_url"] = env_vars.get("ANTHROPIC_BASE_URL", "")
        info.model = env_vars.get("ANTHROPIC_MODEL")

    # Check cc2f variant
    cc2f_path = HOME / ".local" / "bin" / "cc2f"
    if cc2f_path.exists():
        info.metadata["cc2f_available"] = True
        try:
            content = cc2f_path.read_text(encoding="utf-8")
            match = re.search(r'CC2_MODEL="([^"]+)"', content)
            if match:
                info.metadata["cc2f_model"] = match.group(1)
        except Exception:
            pass

    logger.info(
        "cli_agent.detected",
        agent="cc2",
        installed=info.is_installed,
        authenticated=info.is_authenticated,
        model=info.model,
    )
    return info


def detect_zai() -> CLIAgentInfo:
    """Detect ZAI MCP server installation."""
    info = CLIAgentInfo(
        name="ZAI",
        cli_command="zai-mcp-server",
        auth_type="none",
        config_path=str(HOME / ".zai"),
    )

    zai_dir = HOME / ".zai"
    info.is_installed = zai_dir.exists()

    if not info.is_installed:
        return info

    # Check for log files (indicates usage)
    logs = sorted(zai_dir.glob("zai-mcp-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if logs:
        info.is_authenticated = True  # ZAI doesn't need auth, just presence
        info.session_count = len(logs)
        info.latest_session = str(logs[0])
        info.metadata["log_count"] = len(logs)

    logger.info(
        "cli_agent.detected",
        agent="zai",
        installed=info.is_installed,
        sessions=info.session_count,
    )
    return info


# --- Public API ---


def detect_all_agents() -> list[CLIAgentInfo]:
    """Detect all known CLI agents and return their status."""
    agents = [
        detect_claude(),
        detect_codex(),
        detect_kimi(),
        detect_cc2(),
        detect_zai(),
    ]
    return agents


def get_agents_summary() -> dict[str, Any]:
    """Return a summary dict suitable for API responses."""
    agents = detect_all_agents()
    return {
        "agents": [
            {
                "name": a.name,
                "cli_command": a.cli_command,
                "auth_type": a.auth_type,
                "is_installed": a.is_installed,
                "is_authenticated": a.is_authenticated,
                "model": a.model,
                "session_count": a.session_count,
                "latest_session": a.latest_session,
                "metadata": a.metadata,
            }
            for a in agents
        ],
        "total_detected": sum(1 for a in agents if a.is_installed),
        "total_authenticated": sum(1 for a in agents if a.is_authenticated),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }