# Jarvis Messaging Service

Connecteurs messagerie : Telegram Bot API, WhatsApp Business Cloud API, Email IMAP/SMTP.

## Setup

```bash
pip install -e ".[dev]"
python -m jarvis_messaging.main
```

##| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut service |
| `/channels` | GET | Statut de chaque canal configuré |
| `/inbox` | GET | Récupérer messages entrants (option: `?channel=telegram`) |
| `/send` | POST | Envoyer message via canal spécifié |

### Exemple envoi Telegram

```bash
curl -X POST http://localhost:8008/send \
 -H "Content-Type: application/json" \
 -d '{"channel": "telegram", "to": "123456789", "content": "Bonjour depuis Jarvis"}'
```

### Exemple inbox

```bash
curl http://localhost:8008/inbox
curl http://localhost:8008/inbox?channel=email
```

## Configuration (env vars)

| Variable | Description |
|----------|-------------|
| `JARVIS_MESSAGING_TELEGRAM_BOT_TOKEN` | Token bot Telegram |
| `JARVIS_MESSAGING_TELEGRAM_CHAT_ID` | Chat ID destination |
| `JARVIS_MESSAGING_WHATSAPP_ACCESS_TOKEN` | Token WhatsApp Business |
| `JARVIS_MESSAGING_WHATSAPP_PHONE_NUMBER_ID` | Phone Number ID WhatsApp |
| `JARVIS_MESSAGING_EMAIL_IMAP_HOST` | Serveur IMAP |
| `JARVIS_MESSAGING_EMAIL_IMAP_USER` | Utilisateur email |
| `JARVIS_MESSAGING_EMAIL_IMAP_PASS` | Mot de passe email |
| `JARVIS_MESSAGING_EMAIL_SMTP_HOST` | Serveur SMTP |
| `JARVIS_MESSAGING_EMAIL_SMTP_USER` | Utilisateur SMTP |
| `JARVIS_MESSAGING_EMAIL_SMTP_PASS` | Mot de passe SMTP |