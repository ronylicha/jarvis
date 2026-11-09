"""Multi-provider LLM router — Claude, Codex, Gemini, Kimi, Ollama."""

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from jarvis_core.config import settings

logger = structlog.get_logger(__name__)

PROVIDERS = ("anthropic", "openai", "google", "moonshot", "ollama")


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

        dispatch = {
            "anthropic": self._chat_anthropic,
            "openai": self._chat_openai,
            "google": self._chat_google,
            "moonshot": self._chat_moonshot,
            "ollama": self._chat_ollama,
        }

        handler = dispatch[prov]
        logger.info("llm.chat_start", provider=prov, messages=len(messages))

        try:
            result = await handler(messages, model=model, max_tokens=max_tokens, temperature=temperature)
            logger.info("llm.chat_done", provider=prov, chars=len(result.content))
            return result
        except Exception as exc:
            logger.error("llm.chat_error", provider=prov, error=str(exc))
            raise LLMRouterError(f"{prov} failed: {exc}") from exc

    # --- Provider implementations ---

    async def _chat_anthropic(
        self, messages: list[dict[str, str]], *, model: str | None, max_tokens: int, temperature: float
    ) -> LLMResponse:
        if not settings.anthropic_api_key:
            raise LLMRouterError("ANTHROPIC_API_KEY not configured")

        # Convert OpenAI-style messages to Anthropic format
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
        text = "".join(p.get("text", "") for p in content_parts if p.get("type") == "text")
        usage = data.get("usage")

        return LLMResponse(
            content=text,
            provider="anthropic",
            model=data.get("model", model or "unknown"),
            usage={"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0)} if usage else None,
        )

    async def _chat_openai(
        self, messages: list[dict[str, str]], *, model: str | None, max_tokens: int, temperature: float
    ) -> LLMResponse:
        if not settings.openai_api_key:
            raise LLMRouterError("OPENAI_API_KEY not configured")

        resp = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "content-type": "application/json"},
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
            usage={"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)} if usage else None,
        )

    async def _chat_google(
        self, messages: list[dict[str, str]], *, model: str | None, max_tokens: int, temperature: float
    ) -> LLMResponse:
        if not settings.google_api_key:
            raise LLMRouterError("GOOGLE_API_KEY not configured")

        # Convert to Gemini format
        contents = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = {"parts": [{"text": msg["content"]}]}
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        gemini_model = model or "gemini-2.0-flash"
        resp = await self._client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent",
            params={"key": settings.google_api_key},
            json={
                "contents": contents,
                "systemInstruction": system_instruction,
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        text = ""
        if candidates and candidates[0].get("content", {}).get("parts"):
            text = "".join(p.get("text", "") for p in candidates[0]["content"]["parts"])

        return LLMResponse(content=text, provider="google", model=gemini_model)

    async def _chat_moonshot(
        self, messages: list[dict[str, str]], *, model: str | None, max_tokens: int, temperature: float
    ) -> LLMResponse:
        if not settings.moonshot_api_key:
            raise LLMRouterError("MOONSHOT_API_KEY not configured")

        resp = await self._client.post(
            "https://api.moonshot.cn/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.moonshot_api_key}", "content-type": "application/json"},
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

    async def _chat_ollama(
        self, messages: list[dict[str, str]], *, model: str | None, max_tokens: int, temperature: float
    ) -> LLMResponse:
        ollama_model = model or settings.ollama_model
        resp = await self._client.post(
            f"{settings.ollama_base_url}/api/chat",
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

    def get_available_providers(self) -> list[dict[str, Any]]:
        """Return list of configured providers with their status."""
        key_map = {
            "anthropic": settings.anthropic_api_key,
            "openai": settings.openai_api_key,
            "google": settings.google_api_key,
            "moonshot": settings.moonshot_api_key,
            "ollama": True,  # Always available if Ollama is running
        }
        return [
            {"name": name, "configured": bool(key_map.get(name)), "default": name == settings.default_provider}
            for name in PROVIDERS
        ]