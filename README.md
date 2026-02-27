# KidTube

KidTube is an open-source FastAPI service for managing kid profiles and allowed YouTube channels, with SQLite persistence and Discord interaction intake for future bot workflows.

## Features (v0.1.0)

- FastAPI backend on Python 3.12
- SQLite persistence (default `/data/kidtube.db`)
- Auto SQL migration runner (`app/db/migrations/*.sql`)
- Structured JSON logs
- Discord interaction endpoint with Ed25519 signature verification
- Docker image + compose deployment examples
- GitHub Actions CI and GHCR publishing workflow

## Quickstart (Docker Compose - simple)

```bash
cp .env.example .env
docker compose -f deploy/docker-compose.simple.yml up -d
curl http://localhost:2018/health
```

Data is persisted to `./data` on the host and mounted to `/data` in the container.

## Traefik deployment example

1. Ensure your Traefik network exists and Traefik is attached to it.
2. Set required variables (`KIDTUBE_HOST`, optional `TRAEFIK_ENTRYPOINT`) in `.env`.
3. Run:

```bash
docker compose -f deploy/docker-compose.traefik.yml up -d
```

This compose example intentionally avoids hardcoded domains.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `KidTube` | Application display name |
| `APP_VERSION` | `0.1.0` | API version label |
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `2018` | Bind port (runtime config) |
| `DATABASE_URL` | `sqlite:////data/kidtube.db` | SQLAlchemy DB URL |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DISCORD_PUBLIC_KEY` | *(empty)* | Discord app public key for Ed25519 verification |
| `YOUTUBE_API_KEY` | *(empty)* | YouTube Data API key (required for handle/video URL resolution and sync) |
| `KIDTUBE_SYNC_ENABLED` | `true` | Enables/disables background periodic channel refresh task |
| `KIDTUBE_SYNC_INTERVAL_SECONDS` | `900` | Background refresh interval for channel/video cache |
| `SYNC_INTERVAL_SECONDS` | `900` | Backward-compatible alias for sync interval |
| `SYNC_MAX_VIDEOS_PER_CHANNEL` | `15` | Max videos fetched per channel during sync |
| `HTTP_TIMEOUT_SECONDS` | `10` | Timeout (seconds) for outbound HTTP requests |

## API endpoints

- `GET /health` → `{"status":"ok"}`
- `GET /ready` → checks DB connectivity
- `GET /version` → semantic version and git sha when available
- `GET /api/kids`
- `POST /api/kids`
- `GET /api/channels`
- `POST /api/channels`
- `GET /api/feed/latest-per-channel`
- `PATCH /api/channels/{id}`
- `POST /api/sync/run` → triggers an immediate refresh pass for eligible channels (`enabled=true`, `allowed=true`, `blocked=false`)
- `POST /discord/interactions`

### Example curl commands

```bash
curl http://localhost:2018/health
curl http://localhost:2018/ready
curl http://localhost:2018/version

curl -X POST http://localhost:2018/api/kids \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ava","daily_limit_minutes":45}'

curl http://localhost:2018/api/kids

curl -X POST http://localhost:2018/api/channels \
  -H 'Content-Type: application/json' \
  -d '{"input":"@SciShowKids","category":"science"}'

curl http://localhost:2018/api/feed/latest-per-channel

curl -X PATCH http://localhost:2018/api/channels/1 \
  -H 'Content-Type: application/json' \
  -d '{"enabled":false,"category":"science"}'

# Allow a channel (whitelist)
curl -X PATCH http://localhost:2018/api/channels/1 \
  -H 'Content-Type: application/json' \
  -d '{"allowed":true}'

# Block a channel with an admin reason (absolute override + cached video purge)
curl -X PATCH http://localhost:2018/api/channels/1 \
  -H 'Content-Type: application/json' \
  -d '{"blocked":true,"blocked_reason":"manual admin block"}'

# Unblock without auto-allowing
curl -X PATCH http://localhost:2018/api/channels/1 \
  -H 'Content-Type: application/json' \
  -d '{"blocked":false}'
```

## Channel allow/block policy

- Default-safe stance: newly created channels have `allowed=false`.
- Kid-facing feed only includes channels where `enabled=true`, `allowed=true`, and `blocked=false`.
- `blocked=true` is an absolute override: blocked channels are excluded from kid-facing feed responses and background sync, and cached videos are purged when a channel is newly blocked.
- Unblocking a channel (`blocked=false`) does **not** auto-allow it.

## Discord verification notes

`POST /discord/interactions` requires valid Discord signature headers:

- `X-Signature-Ed25519`
- `X-Signature-Timestamp`

The endpoint validates the request using `DISCORD_PUBLIC_KEY`. Invalid signatures return `401`.

## Data persistence

- Default SQLite file path: `/data/kidtube.db`
- Docker examples mount host `./data` to `/data`

## Local development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
uvicorn app.main:app --host 0.0.0.0 --port 2018 --reload
```

## Quality checks

```bash
ruff check .
black --check .
pytest
```

## CI and release tagging

- CI workflow (`.github/workflows/ci.yml`) runs on pushes + PRs and executes Ruff + pytest.
- Docker publish workflow (`.github/workflows/docker-publish.yml`):
  - Push to `main` → tags `:main` and `:sha-<fullsha>`
  - Tag `v*.*.*` → tags version and `:latest`
