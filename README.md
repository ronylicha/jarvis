# ◈ Jarvis — AI Personal Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Node 22+](https://img.shields.io/badge/node-22+-green.svg)](https://nodejs.org/)
[![Tauri v2](https://img.shields.io/badge/Tauri-v2-orange.svg)](https://tauri.app/)

Assistant IA personnel local avec interface HUD sci-fi, voix locale (STT/TTS), orchestration multi-agents, mémoire globale partagée et contrôle PC.

## Features

- **️ Voix 100% locale** : STT whisper.cpp (AVX2) + TTS Piper (~600 MB RAM combiné)
- ** 8 providers LLM** : Claude, Codex/GPT, Gemini, Kimi, MiniMax, GLM/Zhipu, OpenRouter, Cheaper Inference
- ** Catalogue modèles & tarifs** : affichage dynamique des prix $/M tokens input/output par modèle
- ** Gestion API keys depuis l'UI** : ajout/suppression/masquage des clés, support OAuth pour Codex/Claude/Gemini
- ** Mémoire globale persistante** : SQLite (faits structurés) + ChromaDB (recherche sémantique vectorielle)
- **️ Contrôle PC** : capture d'écran, presse-papiers, notifications système, gestion fenêtres
- ** Interface HUD sci-fi** : Tauri v2 transparent, orb animé, design spécifique par agent
- **⚡ Démarrage au boot** : systemd user units + autostart desktop
- ** Sécurité** : auth token, SSRF prevention, shell allowlist, filesystem sandbox

## ️ Architecture

```
jarvis/
├── apps/
│   ├── ui/              # Tauri v2 + React 19 (HUD interface)
│   └── core/            # Python FastAPI — LLM router + orchestration (:8003)
├── services/
│   ├── stt/             # whisper.cpp wrapper — STT local (:8001)
│   ├── tts/             # Piper TTS wrapper — TTS local (:8002)
│   ├── memory/          # SQLite + ChromaDB — mémoire persistante (:8004)
│   ├── connectors/      # Google Workspace, filesystem, shell-safe (:8005)
│   └── pc-actions/      # Screen capture, clipboard, notifications, windows (:8006)
├── scripts/             # Installation & setup
├── systemd/             # User units pour boot automatique
└── data/                # Modèles IA, screenshots, mémoire
```

## Providers & Tarifs

| Provider | Auth | Modèles | Prix Input $/M | Tags |
|----------|------|---------|----------------|------|
| **Claude** | API Key | Opus 4, Sonnet 4, Haiku 3.5 | $0.80 – $15 | flagship, reasoning |
| **Codex / GPT** | OAuth | o3, GPT-4o, Codex Mini | $0.15 – $2.50 | coding, balanced |
| **Gemini** | OAuth | 2.5 Pro, 2.0 Flash, Flash Lite | $0.075 – $1.25 | 1M-context, cheap |
| **Kimi** | API Key | K2, Moonshot 128K/8K | $0.20 – $0.80 | coding, long-context |
| **MiniMax** | API Key | M1, ABAB7 | $0.10 – $0.55 | 1M-context, reasoning |
| **GLM (Zhipu)** | API Key | GLM-4 Plus/Flash, CodeGeeX | Free – $0.70 | free, coding |
| **OpenRouter** | API Key | Llama Sou o Claude Fable 5.1, modelo da Anthropic, operado pela GhostCLI. Como posso ajudar?3, DeepSeek R1 | $0.14 – $0.55 | open-source |
| **Cheaper Inference** | API Key | Llama 3.3 70B, Qwen 2.5 | $0.03 – $0.04 | ultra-cheap |

## 🚀 Installation Automatique (One Command)

**Tout est automatique et résiste au reboot.** Une seule commande installe, compile, configure le boot et lance Jarvis :

```bash
cd ~/projects/jarvis
bash scripts/auto-setup.sh
```

Ce script fait automatiquement :
1. ✅ Installe les dépendances système (scrot, xclip, cmake, etc.)
2. ✅ Crée le venv Python et installe les 7 services
3. ✅ Compile whisper.cpp avec AVX2 et télécharge les modèles voix
4. ✅ Installe Piper TTS et les voix françaises
5. ✅ Build l'UI Tauri en release (binaire natif)
6. ✅ Configure 7 systemd user units + linger (démarrage au boot)
7. ✅ Crée l'autostart XDG desktop (UI fullscreen au login)
8. ✅ Lance tous les services immédiatement

### Résistance au Reboot

| Mécanisme | Ce qu'il fait |
|-----------|---------------|
| **systemd linger** | Les services démarrent au boot système, pas seulement au login |
| **systemd user units** | 7 services redémarrent automatiquement après crash (`Restart=on-failure`) |
| **XDG autostart** | L'UI Jarvis se lance en fullscreen 5s après le login |
| **Health checks** | Chaque service expose `/health` pour monitoring |

### Prérequis

- **OS** : Linux (Zorin/Ubuntu/Fedora) ou macOS
- **CPU** : x86_64 avec AVX2 (ou ARM64 NEON)
- **RAM** : 16 GB minimum, 32 GB recommandé
- **Dev tools** : Node.js 22+, Python 3.12+, Rust/Cargo, pnpm

### Installation Manuelle (optionnelle)

```bash
# 1. Python venv + services
python3 -m venv .venv && source .venv/bin/activate
pip install -e services/stt -e services/tts -e services/memory \
            -e services/connectors -e services/pc-actions \
            -e services/agent-sessions -e apps/core

# 2. Binaires voix
./services/stt/scripts/build_whisper.sh
./services/stt/scripts/download_model.sh
./services/tts/scripts/install_piper.sh
./services/tts/scripts/download_voices.sh

# 3. UI
pnpm install
cd apps/ui && pnpm tauri build

# 4. Boot automatique
bash scripts/setup-boot.sh
```

## API Services

| Service | Port | Endpoints clés |
|---------|------|----------------|
| STT | 8001 | `POST /transcribe`, `WS /transcribe-stream` |
| TTS | 8002 | `POST /speak`, `GET /voices` |
| Core (LLM) | 8003 | `POST /chat`, `POST /chat/stream` (SSE), `GET /providers` |
| Memory | 8004 | `POST /remember`, `POST /recall`, `DELETE /memories/{id}` |
| Connectors | 8005 | `POST /shell/exec`, `POST /fs/read`, `GET /google/calendar` |
| PC Actions | 8006 | `POST /screenshot`, `GET/POST /clipboard`, `POST /notify`, `GET /windows` |
| Agent Sessions | 8007 | `GET /sessions`, `GET /sessions/stream` (SSE), `GET /proxy/status` |

### Exemples

```bash
# Transcription vocale
curl -X POST http://localhost:8001/transcribe \
  -F "file=@audio.wav"

# Synthèse vocale
curl -X POST http://localhost:8002/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Bonjour, je suis Jarvis."}' --output response.wav

# Chat avec Claude
curl -X POST http://localhost:8003/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Quelle heure est-il ?"}], "provider": "anthropic"}'

# Stocker une mémoire
curl -X POST http://localhost:8004/remember \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "claude", "content": "Rony préfère les réponses concises", "tags": ["preference"]}'

# Capture d'écran
curl -X POST http://localhost:8006/screenshot

# Notification desktop
curl -X POST http://localhost:8006/notify \
  -H "Content-Type: application/json" \
  -d '{"title": "Jarvis", "body": "Tâche terminée !"}'
```

## ⌨️ Raccourcis

| Raccourci | Action |
|-----------|--------|
| `Ctrl+Space` | Focus / toggle fenêtre Jarvis |

## Sécurité

- **Auth token** : header `X-Jarvis-Token` sur tous les services sensibles (Memory, Connectors, PC Actions)
- **Shell** : allowlist stricte — seules les commandes whitelistées sont exécutées via `create_subprocess_exec` (pas de shell)
- **Filesystem** : lecture seule dans `~/Documents`, `~/Projects`, `~/Desktop` uniquement
- **SSRF** : Ollama URL validée contre localhost-only allowlist au démarrage
- **Clés API** : passées en headers (jamais en query params), masquables dans l'UI
- **Resource limits** : taille audio max, clipboard max, timeout commandes shell

## ️ Stack Technique

| Composant | Technologie |
|-----------|-------------|
| UI Desktop | Tauri v2 + React 19 + Tailwind CSS v4 |
| STT Local | whisper.cpp (C++, AVX2, MIT) |
| TTS Local | Piper TTS (ONNX, MIT) |
| Mémoire | SQLite + ChromaDB (all-MiniLM-L6-v2) |
| LLM Router | FastAPI + httpx (8 providers) |
| PC Actions | Pillow + xclip + wmctrl + notify-send |
| Monorepo | pnpm + Turbo |
| Backend | Python 3.12 + FastAPI |
| Frontend | TypeScript 5.8 strict |

## Licence

[MIT](LICENSE) — Copyright © 2026 ronylicha

## Contribuer

Les contributions sont bienvenues ! Ouvrez une issue ou une PR.

## Remerciements

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) — STT local performant
- [Piper TTS](https://github.com/rhasspy/piper) — TTS léger et rapide
- [Tauri](https://tauri.app/) — Framework desktop natif léger
- [ChromaDB](https://www.trychroma.com/) — Base vectorielle locale
- [LangGraph](https://github.com/langchain-ai/langgraph) — Inspiration orchestration multi-agents