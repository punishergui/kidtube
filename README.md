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

## API endpoints

- `GET /health` → `{"status":"ok"}`
- `GET /ready` → checks DB connectivity
- `GET /version` → semantic version and git sha when available
- `GET /api/kids`
- `POST /api/kids`
- `GET /api/channels`
- `POST /api/channels`
- `PATCH /api/channels/{id}`
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
  -d '{"input":"@SciShowKids"}'

curl -X PATCH http://localhost:2018/api/channels/1 \
  -H 'Content-Type: application/json' \
  -d '{"enabled":false,"category":"science"}'
```

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
