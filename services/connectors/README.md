# Jarvis Connectors Service

Ponts sécurisés vers Google Workspace, filesystem local et shell.

## Setup

```bash
pip install -e ".[dev]"
python -m jarvis_connectors.main
```

##| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut connecteurs |
| `/shell/exec` | POST | Exécution commande shell (allowlist uniquement| `/fs/read` | POST | Lecture fichier (dossiers autorisés uniquement) |
| `/fs/list` | GET | Listing répertoire (dossiers autorisés uniquement| `/google/calendar` | GET | Événements Google Calendar (OAuth2 requis) |

## Sécurité

- **Authentification** : header `X-Jarvis-Token` (env `JARVIS_CONNECTORS_API_TOKEN`)
- **Shell** : allowlist stricte — seules les commandes listées sont exécutées
- **Filesystem** : lecture seule dans `~/Documents`, `~/Projects`, `~/Desktop`
- **Google** : OAuth2 credentials stockés dans `data/connectors/`

## Configuration (env vars)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JARVIS_CONNECTORS_PORT` | 8005 | Port serveur |
| `JARVIS_CONNECTORS_API_TOKEN` | *(vide)* | Token auth (vide = désactivé) |
| `JARVIS_CONNECTORS_SHELL_TIMEOUT_SECONDS` | 30 | Timeout commandes shell |