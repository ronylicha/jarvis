# Jarvis Memory Service

Mémoire globale persistante + vectorielle partagée entre tous les agents IA.

## Architecture

- **SQLite** : faits structurés, requêtes exactes, audit trail
- **ChromaDB** : embeddings sémantiques, recherche par similarité cosine
- **Double écriture** : chaque `remember()` écrit dans les deux stores simultanément

## Setup

```bash
pip install -e ".[dev]"
python -m jarvis_memory.main
```

Les données sont stockées dans `~/projects/jarvis/data/memory/` (auto-créé).

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Statut + stats store |
| `/remember` | POST | Stocker une mémoire (agent_id + content + metadata/tags) |
| `/recall` | POST | Recherche sémantique (query + filtres agent/tags) |
| `/memories/{id}` | GET | Récupérer une mémoire par ID |
| `/memories/{id}` | DELETE | Supprimer une mémoire |
| `/agents` | GET | Lister tous les agent_id ayant des mémoires |
| `/stats` | GET | Statistiques détaillées du store |

### Exemple remember

```bash
curl -X POST http://localhost:8004/remember \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "claude", "content": "Rony préfère les réponses concises", "tags": ["preference"]}'
```

### Exemple recall

```bash
curl -X POST http://localhost:8004/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "préférences utilisateur", "limit": 5}'
```

## Configuration (env vars)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JARVIS_MEMORY_PORT` | 8004 | Port serveur |
| `JARVIS_MEMORY_EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Modèle embeddings (~90 MB) |
| `JARVIS_MEMORY_DEFAULT_RECALL_LIMIT` | 5 | Résultats par défaut /recall |
| `JARVIS_MEMORY_MAX_RECALL_RESULTS` | 20 | Max résultats /recall |