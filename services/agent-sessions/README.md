# Jarvis Agent Sessions Service

Découverte en temps réel des sessions agents actives (Claude, Codex, Kimi, ZAI) avec support du relay token ghostcli.

## Setup

```bash
pip install -e ".[dev]"
python -m jarvis_agent_sessions.main
```

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut service + proxy relay |
| `/sessions` | GET | Toutes les sessions actives (snapshot) |
| `/sessions/stream` | GET | SSE temps réel (snapshot toutes les 5s) |
| `/proxy/status` | GET | Statut relay ghostcli + config token counting |

### Exemple sessions

```bash
curl http://localhost:8007/sessions | jq '.sessions[] | {agent_type, pid, model, proxy_url}'
```

### Exemple stream SSE

```bash
curl -N http://localhost:8007/sessions/stream
# data: {"sessions": [...], "total_active": 3, "by_agent": {...}}\n\n
```

## Agents détectés

| Agent | Détection | Source modèle | Proxy |
|-------|-----------|---------------|-------|
| Claude Code | Processus `claude` + session JSONL | CLI arg / env ANTHROPIC_MODEL | usage-shim :4748 ou ANTHROPIC_BASE_URL |
| Codex | Processus `codex` (hors chrome/extension) | ~/.codex/config.toml | usage-shim :4748 |
| Kimi | Processus `kimi` | ~/.kimi/config.toml | — |
| ZAI | Processus `zai-mcp-server` | ~/.zai/*.log | — |

## GhostCLI Proxy Relay

Le service détecte automatiquement le relay `usage-shim.ts --serve` (port 4748) qui corrige les compteurs de tokens ghostcli. Quand actif :
- Les sessions Claude/Codex affichent `proxy_url: http://127.0.0.1:4748`
- Le token counting passe par le relay (pas directement par ghostcli.cloud)
- `/proxy/status` retourne le PID du relay et l'URL upstream

## Configuration (env vars)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JARVIS_AGENT_SESSIONS_PORT` | 8007 | Port serveur |
| `JARVIS_AGENT_SESSIONS_API_TOKEN` | *(vide)* | Token auth (vide = désactivé) |
| `JARVIS_AGENT_SESSIONS_GHOSTCLI_BASE_URL` | https://ghostcli.cloud | URL upstream ghostcli |
| `JARVIS_AGENT_SESSIONS_USAGE_SHIM_URL` | http://127.0.0.1:4748 | URL relay usage-shim |
| `JARVIS_AGENT_SESSIONS_SCAN_INTERVAL_SECONDS` | 5.0 | Intervalle scan SSE |