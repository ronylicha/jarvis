# Jarvis Core

Orchestrateur central + routeur multi-provider LLM pour Jarvis.

## Providers supportés

| Provider | Clé env | Modèle défaut | Notes |
|----------|---------|---------------|-------|
| Anthropic (Claude) | `JARVIS_CORE_ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 | Recommandé |
| OpenAI (Codex/GPT) | `JARVIS_CORE_OPENAI_API_KEY` | gpt-4o | Codex via OpenAI API |
| Google (Gemini) | `JARVIS_CORE_GOOGLE_API_KEY` | gemini-2.0-flash | Gratuit tier disponible |
| Moonshot (Kimi) | `JARVIS_CORE_MOONSHOT_API_KEY` | moonshot-v1-8k | Chinois + multilingue |
| Ollama (local) |2.5:7b-q4_K_M | Fallback offline, à installer plus tard |

## Setup

```bash
pip install -e ".[dev]"

# Configurer au moins une clé API
export JARVIS_CORE_ANTHROPIC_API_KEY="sk-ant-..."

python -m jarvis_core.main
```

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut + providers configurés |
| `/providers` | GET | Liste détaillée des providers |
| `/chat` | POST | Route vers un LLM (format OpenAI messages) |

### Exemple chat

```bash
curl -X POST http://localhost:8003/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Quelle heure est-il ?"}],
    "provider": "anthropic"
  }'
```

## Configuration (env vars)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JARVIS_CORE_PORT` | 8003 | Port serveur |
| `JARVIS_CORE_DEFAULT_PROVIDER` | anthropic | Provider par défaut |
| `JARVIS_CORE_REQUEST_TIMEOUT_SECONDS` | 60 | Timeout requêtes LLM |
| `JARVIS_CORE_OLLAMA_BASE_URL` | http://localhost:11434 | URL Ollama local |
| `JARVIS_CORE_OLLAMA_MODEL` | qwen2.5:7b-q4_K_M | Modèle Ollama fallback |