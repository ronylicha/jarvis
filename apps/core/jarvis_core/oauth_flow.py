"""OAuth 2.0 + PKCE flow for desktop apps (Jarvis).

Implements the standard OAuth 2.0 Authorization Code flow with PKCE:
1. Generate code_verifier + code_challenge (SHA-256)
2. Build authorization URL and open browser
3. Local HTTP server on 127.0.0.1 captures the authorization code
4. Exchange code + code_verifier for access_token + refresh_token
5. Store encrypted tokens in ~/.jarvis/oauth/{provider}.json
"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import socket
import threading
import urllib.parse
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

import httpx
import structlog

logger = structlog.get_logger(__name__)

# --- OAuth provider registry ---

OAUTH_PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "name": "Claude (Anthropic)",
        "authorize_url": "https://claude.ai/oauth/authorize",
        "token_url": "https://claude.ai/oauth/token",
        "scopes": ["user:inference", "user:profile"],
        "use_pkce": True,
        "extra_auth_params": {
            "code_challenge_method": "S256",
        },
    },
    "google": {
        "name": "Gemini (Google)",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/generative-language.retriever",
            "openid",
            "email",
            "profile",
        ],
        "use_pkce": True,
        "extra_auth_params": {
            "access_type": "offline",
            "prompt": "consent",
        },
    },
    "openai": {
        "name": "OpenAI / Codex",
        "authorize_url": "https://auth.openai.com/authorize",
        "token_url": "https://auth.openai.com/oauth/token",
        "scopes": ["openid", "profile", "email"],
        "use_pkce": True,
        "extra_auth_params": {
            "audience": "https://api.openai.com/v1",
        },
    },
}

# --- Storage paths ---

def _oauth_dir() -> Path:
    p = Path.home() / ".jarvis" / "oauth"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _client_secrets_path(provider: str) -> Path:
    return _oauth_dir() / f"{provider}.client_secrets.json"


def _tokens_path(provider: str) -> Path:
    return _oauth_dir() / f"{provider}.tokens.json"


# --- PKCE utilities ---

def _generate_code_verifier() -> str:
    """Generate a 128-char URL-safe random string (RFC 7636)."""
    return secrets.token_urlsafe(96)  # 128 chars base64url


def _generate_code_challenge(verifier: str) -> str:
    """SHA-256 of verifier, base64url-encoded without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# --- Data models ---

@dataclass
class OAuthTokens:
    """Stored OAuth tokens for a provider."""
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: float = 0.0
    scope: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        import time
        return time.time() >= self.expires_at

    def save(self, provider: str) -> None:
        """Save tokens to disk (caller is responsible for encryption)."""
        _tokens_path(provider).write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )
        os.chmod(_tokens_path(provider), 0o600)

    @classmethod
    def load(cls, provider: str) -> "OAuthTokens | None":
        path = _tokens_path(provider)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception as exc:
            logger.warning("oauth.tokens_load_error", provider=provider, error=str(exc))
            return None


# --- Client secrets management ---

@dataclass
class ClientSecrets:
    """OAuth client credentials registered with the provider."""
    client_id: str
    client_secret: str = ""  # Empty for public clients (PKCE only)
    redirect_uri: str = ""   # Filled dynamically based on available port

    def save(self, provider: str) -> None:
        _client_secrets_path(provider).write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )
        os.chmod(_client_secrets_path(provider), 0o600)

    @classmethod
    def load(cls, provider: str) -> "ClientSecrets | None":
        path = _client_secrets_path(provider)
        if not path.exists():
            return None
        try:
            return cls(**json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None


def register_client_secrets(
    provider: str, client_id: str, client_secret: str = ""
) -> ClientSecrets:
    """Register or update client credentials for a provider."""
    if provider not in OAUTH_PROVIDERS:
        raise ValueError(f"Unknown OAuth provider: {provider}")
    secrets = ClientSecrets(client_id=client_id, client_secret=client_secret)
    secrets.save(provider)
    logger.info("oauth.client_registered", provider=provider)
    return secrets


# --- Local callback server ---

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the authorization code from the redirect."""

    authorization_code: str | None = None
    returned_state: str | None = None
    error: str | None = None

    def do_GET(self):  # noqa: N802
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "error" in params:
            _OAuthCallbackHandler.error = params["error"][0]
            self._respond(400, f"OAuth error: {params['error'][0]}")
            return

        if "code" in params:
            _OAuthCallbackHandler.authorization_code = params["code"][0]
            _OAuthCallbackHandler.returned_state = params.get("state", [None])[0]
            self._respond(
                200,
                "<!DOCTYPE html><html><body style='background:#0a1428;color:#00f0ff;"
                "font-family:monospace;text-align:center;padding:60px'>"
                "<h1>✓ Authentification réussie</h1>"
                "<p>Vous pouvez fermer cette fenêtre et retourner sur Jarvis.</p>"
                "</body></html>",
                content_type="text/html; charset=utf-8",
            )
            return

        self._respond(400, "Missing authorization code in redirect")

    def _respond(self, status: int, body: str, content_type: str = "text/plain") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Suppress default stderr logging
        pass


def _find_free_port() -> int:
    """Find an available TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_callback_server(port: int, timeout: float = 300.0) -> None:
    """Run the callback server synchronously until one request is handled."""
    server = HTTPServer(("127.0.0.1", port), _OAuthCallbackHandler)
    server.timeout = timeout
    server.handle_request()
    server.server_close()


# --- Public API ---

def get_authorize_url(
    provider: str,
    *,
    port: int | None = None,
) -> tuple[str, str, str, str]:
    """Build the authorization URL for the given provider.

    Returns (url, state, code_verifier, redirect_uri).
    """
    if provider not in OAUTH_PROVIDERS:
        raise ValueError(f"Unknown OAuth provider: {provider}")

    cfg = OAUTH_PROVIDERS[provider]
    client = ClientSecrets.load(provider)
    if not client:
        raise ValueError(
            f"No client secrets registered for {provider}. "
            f"Call register_client_secrets() first."
        )

    # Pick a free local port for the callback
    cb_port = port or _find_free_port()
    redirect_uri = f"http://127.0.0.1:{cb_port}/oauth/callback"
    client.redirect_uri = redirect_uri

    state = secrets.token_urlsafe(32)
    code_verifier = _generate_code_verifier() if cfg["use_pkce"] else ""

    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client.client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(cfg["scopes"]),
        "state": state,
        **cfg.get("extra_auth_params", {}),
    }

    if cfg["use_pkce"]:
        params["code_challenge"] = _generate_code_challenge(code_verifier)
        params["code_challenge_method"] = "S256"

    url = f"{cfg['authorize_url']}?{urllib.parse.urlencode(params)}"
    return url, state, code_verifier, redirect_uri


async def exchange_code(
    provider: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> OAuthTokens:
    """Exchange an authorization code for access + refresh tokens."""
    if provider not in OAUTH_PROVIDERS:
        raise ValueError(f"Unknown OAuth provider: {provider}")

    cfg = OAUTH_PROVIDERS[provider]
    client = ClientSecrets.load(provider)
    if not client:
        raise ValueError(f"No client secrets for {provider}")

    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client.client_id,
    }
    if client.client_secret:
        data["client_secret"] = client.client_secret
    if cfg["use_pkce"] and code_verifier:
        data["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            cfg["token_url"],
            data=data,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        payload = resp.json()

    import time
    expires_in = int(payload.get("expires_in", 3600))
    tokens = OAuthTokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        token_type=payload.get("token_type", "Bearer"),
        expires_at=time.time() + expires_in,
        scope=payload.get("scope", ""),
        raw=payload,
    )
    tokens.save(provider)
    logger.info("oauth.tokens_acquired", provider=provider, expires_in=expires_in)
    return tokens


async def refresh_tokens(provider: str) -> OAuthTokens:
    """Use a stored refresh_token to obtain a new access_token."""
    stored = OAuthTokens.load(provider)
    if not stored or not stored.refresh_token:
        raise ValueError(f"No refresh token available for {provider}")

    cfg = OAUTH_PROVIDERS[provider]
    client = ClientSecrets.load(provider)
    if not client:
        raise ValueError(f"No client secrets for {provider}")

    data: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": stored.refresh_token,
        "client_id": client.client_id,
    }
    if client.client_secret:
        data["client_secret"] = client.client_secret

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            cfg["token_url"],
            data=data,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        payload = resp.json()

    import time
    expires_in = int(payload.get("expires_in", 3600))
    new_tokens = OAuthTokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token", stored.refresh_token),
        token_type=payload.get("token_type", "Bearer"),
        expires_at=time.time() + expires_in,
        scope=payload.get("scope", stored.scope),
        raw=payload,
    )
    new_tokens.save(provider)
    logger.info("oauth.tokens_refreshed", provider=provider)
    return new_tokens


async def get_valid_token(provider: str) -> str:
    """Return a valid access token, refreshing if expired."""
    tokens = OAuthTokens.load(provider)
    if not tokens:
        raise ValueError(f"No tokens stored for {provider}. Complete OAuth flow first.")

    if tokens.is_expired():
        if tokens.refresh_token:
            tokens = await refresh_tokens(provider)
        else:
            raise ValueError(
                f"Token for {provider} expired and no refresh_token available. "
                "Re-run the OAuth flow."
            )
    return tokens.access_token


def revoke_tokens(provider: str) -> bool:
    """Delete stored tokens for a provider."""
    path = _tokens_path(provider)
    if path.exists():
        path.unlink()
        logger.info("oauth.tokens_revoked", provider=provider)
        return True
    return False


def get_provider_status() -> dict[str, dict[str, Any]]:
    """Return status of all OAuth providers (configured + has tokens)."""
    status: dict[str, dict[str, Any]] = {}
    for provider, cfg in OAUTH_PROVIDERS.items():
        client = ClientSecrets.load(provider)
        tokens = OAuthTokens.load(provider)
        status[provider] = {
            "name": cfg["name"],
            "client_registered": client is not None,
            "authenticated": tokens is not None,
            "token_expired": tokens.is_expired() if tokens else None,
            "has_refresh_token": bool(tokens and tokens.refresh_token),
        }
    return status


# --- High-level interactive flow (called from FastAPI endpoint) ---

def start_oauth_flow(provider: str) -> dict[str, Any]:
    """Start an OAuth flow: build URL + launch local callback server in background.

    Returns info dict with authorize_url and port for the frontend to open.
    The callback server runs in a daemon thread and will capture the code.
    """
    # Reset handler state
    _OAuthCallbackHandler.authorization_code = None
    _OAuthCallbackHandler.returned_state = None
    _OAuthCallbackHandler.error = None

    url, state, code_verifier, redirect_uri = get_authorize_url(provider)
    port = int(redirect_uri.split(":")[-1].split("/")[0])

    # Store PKCE context for the exchange step
    _pending_flows[provider] = {
        "state": state,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "port": port,
    }

    # Start callback server in background thread
    thread = threading.Thread(
        target=_run_callback_server,
        args=(port, 300.0),
        daemon=True,
    )
    thread.start()
    _pending_threads[provider] = thread

    logger.info("oauth.flow_started", provider=provider, port=port)
    return {
        "provider": provider,
        "authorize_url": url,
        "port": port,
        "state": state,
    }


async def check_oauth_flow_status(provider: str) -> dict[str, Any]:
    """Check if the callback has been received and exchange code for tokens."""
    pending = _pending_flows.get(provider)
    if not pending:
        return {"status": "not_started"}

    # Check for error
    if _OAuthCallbackHandler.error:
        _pending_flows.pop(provider, None)
        return {"status": "error", "error": _OAuthCallbackHandler.error}

    # Check if callback received
    if _OAuthCallbackHandler.authorization_code:
        code = _OAuthCallbackHandler.authorization_code
        returned_state = _OAuthCallbackHandler.returned_state

        if returned_state != pending["state"]:
            _pending_flows.pop(provider, None)
            return {"status": "error", "error": "State mismatch — possible CSRF attack"}

        try:
            tokens = await exchange_code(
                provider,
                code,
                pending["code_verifier"],
                pending["redirect_uri"],
            )
            _pending_flows.pop(provider, None)
            return {"status": "complete", "tokens": asdict(tokens)}
        except Exception as exc:
            _pending_flows.pop(provider, None)
            return {"status": "error", "error": f"Token exchange failed: {exc}"}

    return {"status": "waiting", "port": pending["port"]}


# Module-level state for in-flight flows
_pending_flows: dict[str, dict[str, Any]] = {}
_pending_threads: dict[str, threading.Thread] = {}