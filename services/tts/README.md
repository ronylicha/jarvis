# Jarvis TTS Service

Text-to-Speech local via **Piper TTS** exposé en API FastAPI.

## Setup

```bash
# 1. Installer le binaire Piper
./scripts/install_piper.sh

# 2. Télécharger les voix françaises
./scripts/download_voices.sh

# 3. Installer les dépendances Python
pip install -e ".[dev]"

# 4. Lancer le service
python -m jarvis_tts.main
```

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut binaire + voix disponibles |
| `/voices` | GET | Liste des voix avec métadonnées |
| `/speak` | POST | Synthèse vocale → retourne WAV |

### Exemple /speak

```bash
curl -X POST http://localhost:8002/speak \
 -H "Content-Type: application/json" \
 -d '{"text": "Bonjour Rony, je suis Jarvis.", "speed": 1.0}' \
 --output response.wav
```

## Configuration (env vars)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JARVIS_TTS_PORT` | 8002 | Port serveur |
| `JARVIS_TTS_DEFAULT_VOICE` | fr_FR-siwis-medium | Voix par défaut |
| `JARVIS_TTS_DEFAULT_SPEED` | 1.0 | Vitesse (0.5–2.0) |
| `JARVIS_TTS_TIMEOUT_SECONDS` | 30 | Timeout synthèse |