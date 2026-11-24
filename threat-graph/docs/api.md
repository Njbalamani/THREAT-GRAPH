# API reference

Base URL: `http://localhost:8000`. Interactive documentation is available at `/docs`.

All endpoints except login, registration admin-only operations noted below, system health, and root require `Authorization: Bearer <access_token>`.

## Auth

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | Public | Form login, returns bearer token |
| GET | `/api/auth/me` | Authenticated | Current user |
| POST | `/api/auth/register` | Admin | Create analyst/admin/viewer user |
| GET | `/api/auth/users` | Admin | List users |

## System and dashboard

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/system/health` | Public | Service health |
| POST | `/api/system/seed-samples` | Analyst+ | Import bundled sample datasets |
| GET | `/api/dashboard/summary` | Authenticated | Counts, charts, model status, recent activity |

## Indicators

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/indicators` | Authenticated | Filter and list indicators |
| GET | `/api/indicators/{id}` | Authenticated | Indicator detail |
| POST | `/api/indicators` | Analyst+ | Create indicator |
| PATCH | `/api/indicators/{id}` | Analyst+ | Update severity, confidence, tags, confirmation |
| DELETE | `/api/indicators/{id}` | Admin | Delete indicator |

Query parameters: `indicator_type`, `severity`, `search`, `limit`, `offset`.

## Ingestion and feeds

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/ingestion/upload` | Analyst+ | Multipart file upload |
| POST | `/api/ingestion/text` | Analyst+ | Ingest pasted content |
| GET | `/api/ingestion/jobs` | Authenticated | Job audit list |
| GET | `/api/ingestion/jobs/{id}` | Authenticated | Job detail |
| GET | `/api/feeds` | Authenticated | List feed configurations |
| POST | `/api/feeds` | Admin | Create feed |
| PATCH | `/api/feeds/{id}` | Admin | Update feed |
| DELETE | `/api/feeds/{id}` | Admin | Delete feed |
| POST | `/api/feeds/{id}/poll` | Analyst+ | Poll one feed |
| POST | `/api/feeds/poll-enabled` | Analyst+ | Poll all enabled feeds |

Supported ingestion formats: JSON, CSV, plain log/text, and STIX bundles. Feed types: STIX, TAXII, JSON, CSV, and log.

## Graph

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/graph/stats` | Authenticated | Graph counts and degree summary |
| GET | `/api/graph/nodes` | Authenticated | List graph nodes |
| GET | `/api/graph/edges` | Authenticated | List graph edges |
| GET | `/api/graph/snapshot` | Authenticated | Nodes and edges for visualization |
| GET | `/api/graph/neighbors` | Authenticated | N-hop neighborhood |
| POST | `/api/graph/path` | Authenticated | Shortest path between node keys |

Every edge includes `provenance`, which is either `observed` or `inferred`.

## Analytics and ML

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/analytics/graph/rebuild` | Analyst+ | Rebuild relationships from events |
| POST | `/api/analytics/graph/analyze` | Authenticated | Clusters, important nodes, anomalies |
| POST | `/api/analytics/model/train` | Analyst+ | Train and persist a risk model |
| GET | `/api/analytics/model` | Authenticated | Current model metadata |
| GET | `/api/analytics/predictions` | Authenticated | Advisory predictions with explanations |

Predictions include `prediction_only: true`, `confirmed: false`, probability, risk level, and explanation text.

## Investigations

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/investigations` | Authenticated | List cases |
| POST | `/api/investigations` | Analyst+ | Create case |
| GET | `/api/investigations/{id}` | Authenticated | Case detail with indicators, notes, timeline |
| PATCH | `/api/investigations/{id}` | Analyst+ | Update title, status, priority, description |
| DELETE | `/api/investigations/{id}` | Analyst+ | Delete case |
| POST | `/api/investigations/{id}/indicators/{indicator_id}` | Analyst+ | Link indicator |
| POST | `/api/investigations/{id}/notes` | Analyst+ | Add note |
| GET | `/api/investigations/{id}/timeline` | Authenticated | Timeline events |

## Reports and exports

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/reports/pdf` | Authenticated | Generate PDF report |
| GET | `/api/exports/indicators.csv` | Authenticated | Export indicators |
| GET | `/api/exports/relationships.csv` | Authenticated | Export relationships |
| GET | `/api/exports/graph.json` | Authenticated | Export graph JSON |
| GET | `/api/exports/graph.graphml` | Authenticated | Export GraphML |

## Error format

Errors use a consistent body:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```
