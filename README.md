# 🤖 Jarvis — AI Personal Assistant

Assistant IA personnel local avec interface HUD, voix locale (STT/TTS), orchestration multi-agents et mémoire globale partagée.

## Architecture

```
jarvis/
├── apps/
│   ├── ui/          # Tauri v2 + React 19 (HUD sci-fi)
│   └── core/        # Python FastAPI orchestrateur
├── services/
│   ├── stt/         # whisper.cpp wrapper (STT local)
│   ├── tts/         # Piper TTS wrapper (TTS local)
│   ├── memory/      # SQLite + ChromaDB (mémoire persistante)
│   └── connectors/  # Google Workspace, filesystem, shell
├── scripts/         # Installation & utilitaires
├── systemd/         # Units systemd user
└── docs/            # Documentation
```

## Stack Technique

| Composant | Technologie | Raison |
|-----------|-------------|--------|
| UI Desktop | Tauri v2 + React 19 + Tailwind v4 | Fenêtre native ~15 MB RAM, transparent, hotkeys globales |
| STT Local | whisper.cpp (AVX2) | Temps réel CPU, ~400 MB RAM, MIT |
| TTS Local | Piper TTS | <100ms latence, voix FR, ~200 MB RAM, MIT |
| Mémoire | SQLite + ChromaDB | Faits structurés + recherche sémantique, persistant |
| Orchestration | LangGraph | Multi-agents stateful, fiabilité production |
| Agents LLM | Claude / Codex / Gemini / Kimi / Ollama | Routage multi-provider, fallback local |
| Monorepo | pnpm + Turbo | Workspaces isolés, build parallèle |

## Prérequis Système

- **OS** : Linux (Zorin/Ubuntu/Fedora) ou macOS
- **CPU** : x86_64 avec AVX2 (ou ARM64 NEON)
- **RAM** : 16 GB minimum, 32 GB recommandé
- **GPU** : Optionnel (CPU-only supporté pour STT/TTS)
- **Dev tools** : Node.js 22+, Python 3.12+, Rust/Cargo, pnpm

## Installation Rapide

```bash
# 1. Cloner et installer
cd ~/projects/jarvis
pnpm install

# 2. Installer les dépendances système
./scripts/install.sh

# 3. Démarrer en développement
pnpm dev

# 4. Configurer le boot automatique
./scripts/setup-boot.sh
```

## Phases de Développement

| Phase | Contenu | Statut |
|-------|---------|--------|
| 0 | Scaffold monorepo + config | ✅ Terminé |
| 1 | Voix locale (STT/TTS) | 🔲 À faire |
| 2 | Cerveau & mémoire | 🔲 À faire |
| 3 | Interface HUD | 🔲 À faire |
| 4 | Connecteurs work | 🔲 À faire |
| 5 | Boot & daemon | 🔲 À faire |

## Licence

MIT