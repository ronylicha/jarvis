# Jarvis STT Service

Speech-to-Text local via **whisper.cpp** exposé en API FastAPI.

## Setup

```bash
# 1. Compiler whisper.cpp avec AVX2
./scripts/build_whisper.sh

# 2. Télécharger le modèle small (~460 MB)
./scripts/download_model.sh

# 3. Installer les dépendances Python
pip install -e ".[dev]"

# 4. Lancer le service
python -m jarvis_stt.main
```

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut binaire + modèle |
| `/transcribe` | POST | Transcription fichier audio (multipart) |
| `/transcribe-stream` | WebSocket | Transcription streaming temps réel |

## Configuration (env vars)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JARVIS_STT_PORT` | 8001 | Port serveur |
| `JARVIS_STT_DEFAULT_LANGUAGE` | fr | Langue par défaut |
| `JARVIS_STT_TIMEOUT_SECONDS` | 30 | Timeout transcription |
| `JARVIS_STT_THREADS` | 4 | Threads CPU |
| `JARVIS_STT_MAX_AUDIO_SIZE_MB` | 25 | Taille max audio |