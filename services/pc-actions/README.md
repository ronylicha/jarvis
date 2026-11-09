# Jarvis PC Actions Service

Contrôle du PC : capture d'écran, presse-papiers, notifications système, gestion fenêtres.

## Setup

```bash
# Dépendances système requises (Zorin/Ubuntu)
sudo apt install scrot xclip wmctrl xdotool libnotify-bin

pip install -e ".[dev]"
python -m jarvis_pc_actions.main
```

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut service |
| `/screenshot` | POST | Capture écran (option: region crop) → base64 PNG |
| `/clipboard` | GET | Lire le presse-papiers texte |
| `/clipboard` | POST | Écrire dans le presse-papiers |
| `/notify` | POST | Notification desktop (title, body, urgency) |
| `/windows` | GET | Lister toutes les fenêtres visibles |
| `/windows/activate` | POST | Activer/focus une fenêtre par ID |
| `/system-info` | GET | Infos système (uptime, disk, memory, active window) |

### Exemples

```bash
# Capture d'écran complète
curl -X POST http://localhost:8006/screenshot

# Capture d'une région
curl -X POST http://localhost:8006/screenshot \
  -H "Content-Type: application/json" \
  -d '{"region": [100, 100, 800, 600]}'

# Notification
curl -X POST http://localhost:8006/notify \
  -H "Content-Type: application/json" \
  -d '{"title": "Jarvis", "body": "Tâche terminée !", "urgency": "normal"}'

# Lire presse-papiers
curl http://localhost:8006/clipboard

# Lister fenêtres
curl http://localhost:8006/windows
```

## Configuration (env vars)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JARVIS_PC_ACTIONS_PORT` | 8006 | Port serveur |
| `JARVIS_PC_ACTIONS_API_TOKEN` | *(vide)* | Token auth (vide = désactivé) |
| `JARVIS_PC_ACTIONS_NOTIFICATION_TIMEOUT_SECONDS` | 5 | Durée notification |
| `JARVIS_PC_ACTIONS_MAX_CLIPBOARD_SIZE_BYTES` | 1000000 | Taille max clipboard |

## Sécurité

- Auth token via header `X-Jarvis-Token`
- Screenshots stockés dans `data/screenshots/` (auto-créé)
- Clipboard limité à 1 MB
- Notifications via `notify-send` uniquement (pas d'injection)