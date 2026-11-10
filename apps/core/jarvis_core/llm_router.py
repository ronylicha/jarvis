"""Multi-provider LLM router — Claude, Codex, Gemini, Kimi, Ollama."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from jarvis_core.config import settings

logger = structlog.get_logger(__name__)

PROVIDERS = ("anthropic", "openai", "google", "moonshot", "minimax", "zhipu", "openrouter", "ollama")

# Per-provider model allowlists — reject unknown models before forwarding to API
_MODEL_ALLOWLISTS: dict[str, frozenset[str]] = {
    "anthropic": frozenset({
        "claude-opus-4-20250514", "claude-sonnet-4-20250514", "claude-haiku-3-5-20241022",
    }),
    "openai": frozenset({
        "o3", "gpt-4o", "gpt-4o-mini", "codex-mini-latest",
    }),
    "google": frozenset({
        "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.5-flash-lite",
    }),
    "moonshot": frozenset({
        "kimi-k2", "moonshot-v1-128k", "moonshot-v1-8k",
    }),
    "minimax": frozenset({
        "MiniMax-M1", "abab7-chat",
    }),
    "zhipu": frozenset({
        "glm-4-plus", "glm-4-flash", "codegeex-4",
    }),
    "openrouter": frozenset({
        "meta-llama/llama-4-maverick", "qwen/qwen3-235b-a22b", "deepseek/deepseek-r1",
    }),
    # Ollama models are local and dynamic — no allowlist enforcement
}

# Allowed hosts for Ollama (local-only)
_ALLOWED_OLLAMA_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _validate_ollama_url(url: str) -> str:
    """Validate Ollama URL is local-only to prevent SSRF.

    Only http://localhost or http://127.0.0.1 are permitted.
    Rejects cloud metadata IPs, private ranges, non-http schemes.
    """
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise ValueError(f"Ollama URL must use http scheme, got: {parsed.scheme}")
    if parsed.hostname not in _ALLOWED_OLLAMA_HOSTS:
        raise ValueError(
            f"Ollama URL must point to localhost/127.0.0.1, got: {parsed.hostname}"
        )
    return url


@dataclass(frozen=True)
class LLMResponse:
    """Unified response from any LLM provider."""

    content: str
    provider: str
    model: str
    usage: dict[str, int] | None = None


class LLMRouterError(Exception):
    """Raised when all providers fail or config is invalid."""


class LLMRouter:
    """Routes chat requests to the configured LLM provider."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
        # Validate Ollama URL at init time — fail fast on misconfiguration
        try:
            self._validated_ollama_url = _validate_ollama_url(settings.ollama_base_url)
        except ValueError as exc:
            logger.warning("llm.ollama_url_invalid", error=str(exc))
            self._validated_ollama_url = None

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request to the specified or default provider."""
        prov = provider or settings.default_provider
        if prov not in PROVIDERS:
            raise LLMRouterError(f"Unknown provider: {prov}. Available: {PROVIDERS}")

        # Validate model against per-provider allowlist before forwarding
        if model is not None and prov in _MODEL_ALLOWLISTS:
            allowed = _MODEL_ALLOWLISTS[prov]
            if model not in allowed:
                raise LLMRouterError(
                    f"Invalid model '{model}' for provider '{prov}'. "
                    f"Allowed: {sorted(allowed)}"
                )

        dispatch = {
            "anthropic": self._chat_anthropic,
            "openai": self._chat_openai,
            "google": self._chat_google,
            "moonshot": self._chat_moonshot,
            "minimax": self._chat_minimax,
            "zhipu": self._chat_zhipu,
            "openrouter": self._chat_openrouter,
            "ollama": self._chat_ollama,
        }

        # Build ordered provider list: requested first, then fallbacks
        fallback_order = [prov] + [p for p in PROVIDERS if p != prov and p != "ollama"]

        last_error: Exception | None = None
        for attempt_prov in fallback_order:
            handler = dispatch.get(attempt_prov)
            if handler is None:
                continue

            # Skip unconfigured providers during fallback
            # Check provider availability (Ollama requires installed models)
            if attempt_prov == "ollama":
                if self._validated_ollama_url is None:
                    continue
                if not await self._ollama_has_models():
                    continue
            else:
                key_map = {
                    "anthropic": settings.anthropic_api_key,
                    "openai": settings.openai_api_key,
                    "google": settings.google_api_key,
                    "moonshot": settings.moonshot_api_key,
                    "minimax": settings.minimax_api_key,
                    "zhipu": settings.zhipu_api_key,
                    "openrouter": settings.openrouter_api_key,
                }
                if not key_map.get(attempt_prov):
                    continue

            # Validate model only for the explicitly requested provider
            if attempt_prov == prov and model is not None and prov in _MODEL_ALLOWLISTS:
                allowed = _MODEL_ALLOWLISTS[prov]
                if model not in allowed:
                    raise LLMRouterError(
                        f"Invalid model '{model}' for provider '{prov}'. "
                        f"Allowed: {sorted(allowed)}"
                    )

            # For fallback providers, use their default model (ignore user's model choice)
            attempt_model = model if attempt_prov == prov else None

            logger.info(
                "llm.chat_start",
                provider=attempt_prov,
                is_fallback=attempt_prov != prov,
                messages=len(messages),
            )

            try:
                result = await handler(
                    messages,
                    model=attempt_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                if attempt_prov != prov:
                    logger.warning(
                        "llm.fallback_used",
                        original=prov,
                        fallback=attempt_prov,
                    )
                logger.info("llm.chat_done", provider=attempt_prov, chars=len(result.content))
                return result
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "llm.chat_retry",
                    provider=attempt_prov,
                    error=str(exc),
                    will_fallback=True,
                )
                continue

        logger.error("llm.all_providers_failed", error=str(last_error))
        raise LLMRouterError(
            f"All providers failed. Last error ({prov}): {last_error}"
        ) from last_error

    # --- Provider implementations ---

    async def _chat_anthropic(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not settings.anthropic_api_key:
            raise LLMRouterError("ANTHROPIC_API_KEY not configured")

        system_msg = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append({"role": msg["role"], "content": msg["content"]})

        resp = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model or "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_msg,
                "messages": user_messages,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        content_parts = data.get("content", [])
        text = "".join(
            p.get("text", "") for p in content_parts if p.get("type") == "text"
        )
        usage = data.get("usage")

        return LLMResponse(
            content=text,
            provider="anthropic",
            model=data.get("model", model or "unknown"),
            usage=(
                {
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                }
                if usage
                else None
            ),
        )

    async def _chat_openai(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not settings.openai_api_key:
            raise LLMRouterError("OPENAI_API_KEY not configured")

        resp = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model or "gpt-4o",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage")

        return LLMResponse(
            content=choice.get("content", ""),
            provider="openai",
            model=data.get("model", model or "unknown"),
            usage=(
                {
                    "input": usage.get("prompt_tokens", 0),
                    "output": usage.get("completion_tokens", 0),
                }
                if usage
                else None
            ),
        )

    async def _chat_google(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not settings.google_api_key:
            raise LLMRouterError("GOOGLE_API_KEY not configured")

        contents = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = {"parts": [{"text": msg["content"]}]}
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        gemini_model = model or "gemini-2.0-flash"
        # SECURITY: API key passed via header, NOT query param (prevents URL/log leakage)
        resp = await self._client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent",
            headers={
                "x-goog-api-key": settings.google_api_key,
                "content-type": "application/json",
            },
            json={
                "contents": contents,
                "systemInstruction": system_instruction,
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        text = ""
        if candidates and candidates[0].get("content", {}).get("parts"):
            text = "".join(
                p.get("text", "") for p in candidates[0]["content"]["parts"]
            )

        return LLMResponse(content=text, provider="google", model=gemini_model)

    async def _chat_moonshot(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not settings.moonshot_api_key:
            raise LLMRouterError("MOONSHOT_API_KEY not configured")

        resp = await self._client.post(
            "https://api.moonshot.cn/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.moonshot_api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model or "moonshot-v1-8k",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        return LLMResponse(
            content=choice.get("content", ""),
            provider="moonshot",
            model=data.get("model", model or "unknown"),
        )

    async def _chat_minimax(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not settings.minimax_api_key:
            raise LLMRouterError("MINIMAX_API_KEY not configured")

        resp = await self._client.post(
            "https://api.minimax.chat/v1/text/chatcompletion_v2",
            headers={
                "Authorization": f"Bearer {settings.minimax_api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model or "MiniMax-M1",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage")

        return LLMResponse(
            content=text,
            provider="minimax",
            model=data.get("model", model or "unknown"),
            usage=(
                {"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)}
                if usage
                else None
            ),
        )

    async def _chat_zhipu(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not settings.zhipu_api_key:
            raise LLMRouterError("ZHIPU_API_KEY not configured")

        # Zhipu/GLM uses OpenAI-compatible API format
        resp = await self._client.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.zhipu_api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model or "glm-4-flash",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage")

        return LLMResponse(
            content=choice.get("content", ""),
            provider="zhipu",
            model=data.get("model", model or "unknown"),
            usage=(
                {"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)}
                if usage
                else None
            ),
        )

    async def _chat_openrouter(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not settings.openrouter_api_key:
            raise LLMRouterError("OPENROUTER_API_KEY not configured")

        # OpenRouter uses OpenAI-compatible API format
        resp = await self._client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "content-type": "application/json",
                "HTTP-Referer": "https://github.com/ronylicha/jarvis",
                "X-Title": "Jarvis AI Assistant",
            },
            json={
                "model": model or "meta-llama/llama-4-maverick",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage")

        return LLMResponse(
            content=choice.get("content", ""),
            provider="openrouter",
            model=data.get("model", model or "unknown"),
            usage=(
                {"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)}
                if usage
                else None
            ),
        )

    async def _chat_ollama(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        # SECURITY: URL validated at init time against localhost allowlist
        if self._validated_ollama_url is None:
            raise LLMRouterError(
                "Ollama URL is invalid or not configured. "
                "Must be http://localhost or http://127.0.0.1"
            )

        ollama_model = model or settings.ollama_model
        resp = await self._client.post(
            f"{self._validated_ollama_url}/api/chat",
            json={
                "model": ollama_model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        message = data.get("message", {})
        return LLMResponse(
            content=message.get("content", ""),
            provider="ollama",
            model=data.get("model", ollama_model),
            usage={
                "input": data.get("prompt_eval_count", 0),
                "output": data.get("eval_count", 0),
            },
        )

    async def fetch_provider_models(self, provider: str) -> list[dict[str, Any]]:
        """Fetch live model list from a provider's /models API endpoint.

        Returns list of dicts with id, name, and optional pricing/context info.
        Raises LLMRouterError if provider unconfigured or API call fails.
        """
        if provider not in PROVIDERS:
            raise LLMRouterError(f"Unknown provider: {provider}")

        api_configs: dict[str, tuple[str, dict[str, str]]] = {
            "anthropic": (
                "https://api.anthropic.com/v1/models",
                {"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"},
            ),
            "openai": (
                "https://api.openai.com/v1/models",
                {"Authorization": f"Bearer {settings.openai_api_key}"},
            ),
            "google": (
                "https://generativelanguage.googleapis.com/v1beta/models",
                {"x-goog-api-key": settings.google_api_key},
            ),
            "moonshot": (
                "https://api.moonshot.cn/v1/models",
                {"Authorization": f"Bearer {settings.moonshot_api_key}"},
            ),
            "minimax": (
                "https://api.minimax.chat/v1/models",
                {"Authorization": f"Bearer {settings.minimax_api_key}"},
            ),
            "zhipu": (
                "https://open.bigmodel.cn/api/paas/v4/models",
                {"Authorization": f"Bearer {settings.zhipu_api_key}"},
            ),
            "openrouter": (
                "https://openrouter.ai/api/v1/models",
                {"Authorization": f"Bearer {settings.openrouter_api_key}"},
            ),
        }

        if provider == "ollama":
            if self._validated_ollama_url is None:
                raise LLMRouterError("Ollama not configured")
            resp = await self._client.get(f"{self._validated_ollama_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [
                {"id": m["name"], "name": m["name"], "size_mb": round(m.get("size", 0) / 1024 / 1024)}
                for m in data.get("models", [])
            ]

        if provider not in api_configs:
            raise LLMRouterError(f"No API config for {provider}")

        url, headers = api_configs[provider]
        key_map = {
            "anthropic": settings.anthropic_api_key,
            "openai": settings.openai_api_key,
            "google": settings.google_api_key,
            "moonshot": settings.moonshot_api_key,
            "minimax": settings.minimax_api_key,
            "zhipu": settings.zhipu_api_key,
            "openrouter": settings.openrouter_api_key,
        }
        if not key_map.get(provider):
            raise LLMRouterError(f"{provider} API key not configured")

        resp = await self._client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        # Normalize different API response formats
        models_raw = data.get("data", data.get("models", []))
        models = []
        for m in models_raw:
            model_id = m.get("id", m.get("name", ""))
            if not model_id:
                continue
            models.append({
                "id": model_id,
                "name": m.get("display_name", m.get("name", model_id)),
                "owned_by": m.get("owned_by", ""),
            })

        logger.info("llm.models_fetched", provider=provider, count=len(models))
        return models

    async def _ollama_has_models(self) -> bool:
        """Check if Ollama has at least one model pulled (not just installed)."""
        if self._validated_ollama_url is None:
            return False
        try:
            resp = await self._client.get(f"{self._validated_ollama_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return len(data.get("models", [])) > 0
        except Exception:
            return False

    async def get_available_providers(self) -> list[dict[str, Any]]:
        """Return list of configured providers with their status.

        Ollama is only marked configured if URL is valid AND models are pulled.
        """
        ollama_configured = await self._ollama_has_models()
        key_map = {
            "anthropic": settings.anthropic_api_key,
            "openai": settings.openai_api_key,
            "google": settings.google_api_key,
            "moonshot": settings.moonshot_api_key,
            "minimax": settings.minimax_api_key,
            "zhipu": settings.zhipu_api_key,
            "openrouter": settings.openrouter_api_key,
            "ollama": ollama_configured,
        }
        return [
            {
                "name": name,
                "configured": bool(key_map.get(name)),
                "default": name == settings.default_provider,
            }
            for name in PROVIDERS
        ]