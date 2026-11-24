# Deployment

## Local development

1. Copy `.env.example` to `.env`.
2. Install backend dependencies into `backend/.venv`.
3. Start the API with `uvicorn app.main:app --reload --port 8000`.
4. Install frontend dependencies with `npm.cmd install`.
5. Start Vite with `npm.cmd run dev`.

For a database-free local start, set `DATABASE_URL=sqlite:///./threatgraph.db` and leave `NEO4J_ENABLED=false`. This uses the NetworkX JSON graph store.

For full graph storage, run Neo4j and set `NEO4J_ENABLED=true` with the matching connection variables.

## Docker Compose

```powershell
docker compose up --build
```

Services:

| Service | Port | Purpose |
| --- | --- | --- |
| `postgres` | 5432 | Relational persistence |
| `neo4j` | 7474 / 7687 | Graph persistence and Cypher |
| `backend` | 8000 | FastAPI application |
| `frontend` | 5173 | React application served by nginx |

Stop and remove volumes:

```powershell
docker compose down -v
```

## Production checklist

- Set a strong random `SECRET_KEY`.
- Replace `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
- Restrict `CORS_ORIGINS` to the deployed frontend origin.
- Use managed PostgreSQL and Neo4j with backups.
- Terminate TLS at a reverse proxy or load balancer.
- Set `NEO4J_ENABLED=true` and verify graph connectivity.
- Mount persistent storage for `GRAPH_STORAGE_PATH` and `MODEL_DIR` even when Neo4j is enabled.
- Run backend checks and frontend build in CI before release.
- Limit feed URLs and credentials to trusted intelligence providers.
- Review investigation access by role; use viewer accounts for read-only users.

## Health checks

- API root: `GET /`
- API health: `GET /health`
- Public system health: `GET /api/system/health`
- Neo4j browser: `http://localhost:7474`

## Backups

Back up the PostgreSQL database, the Neo4j data volume, the NetworkX graph file, and the model artifact directory together. Restoring only one store can leave relationships or model metadata inconsistent.
