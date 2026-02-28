# KidTube

KidTube is a FastAPI app that gives kids a curated YouTube feed with parent-managed limits, schedules, bedtime windows, and PIN-protected profile switching.

## Quick Start

### Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
uvicorn app.main:app --host 0.0.0.0 --port 2018 --reload
```

Open `http://localhost:2018`, then visit `/admin` for parent pages.

### Checks

```bash
ruff check .
pytest
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `2018` | Bind port |
| `KIDTUBE_DB_PATH` | `./data/kidtube.db` | Preferred SQLite DB path |
| `SQLITE_PATH` | *(empty)* | Legacy DB path fallback |
| `DATABASE_URL` | `sqlite:///<resolved DB path>` | SQLAlchemy URL (overrides path envs if set) |
| `SECRET_KEY` | *(required in production)* | Session signing |
| `YOUTUBE_API_KEY` | *(empty)* | Channel lookup + sync |
| `DISCORD_PUBLIC_KEY` | *(empty)* | Discord signature verification |
| `DISCORD_APPROVAL_WEBHOOK_URL` | *(empty)* | Post approval events to Discord |
| `KIDTUBE_SYNC_ENABLED` | `true` | Background sync on/off |
| `KIDTUBE_SYNC_INTERVAL_SECONDS` | `900` | Background sync interval |
| `SYNC_MAX_VIDEOS_PER_CHANNEL` | `15` | Max videos/channel per sync |

DB path resolution precedence for startup is:
1. `KIDTUBE_DB_PATH`
2. `SQLITE_PATH`
3. `./data/kidtube.db`

## Docker (non-root)

The image runs as non-root user `kidtube` (UID/GID defaults to `10001`).

```bash
docker build -t kidtube .
docker run --rm -p 2018:2018 \
  -e KIDTUBE_DB_PATH=/data/kidtube.db \
  -v "$(pwd)/data:/data" \
  kidtube
```

If host volume permissions are strict, align IDs:

```bash
docker build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g) -t kidtube .
```

Make sure mounted `/data` is writable by the container user.

### Homelab/Traefik compose patch snippet (documentation only)

Do **not** replace your existing compose file; only add the equivalent env/volume/user bits:

```yaml
services:
  kidtube:
    environment:
      - KIDTUBE_DB_PATH=/data/kidtube.db
    volumes:
      - ./kidtube-data:/data
    user: "10001:10001"
```

## Backups (SQLite)

### Manual backup from running container

```bash
docker exec <kidtube-container> python -m app.tools.backup_db \
  --src /data/kidtube.db \
  --out /data/backups/kidtube-$(date +%Y%m%d-%H%M).db
```

### Restore

1. Stop the KidTube container.
2. Replace the DB with a backup file.
3. Start the container.

```bash
docker stop <kidtube-container>
cp ./kidtube-data/backups/kidtube-YYYYMMDD-HHMM.db ./kidtube-data/kidtube.db
docker start <kidtube-container>
```

### Optional cron example (host)

```bash
# every day at 03:15
15 3 * * * docker exec kidtube python -m app.tools.backup_db --src /data/kidtube.db --out /data/backups/kidtube-$(date +\%Y\%m\%d-\%H\%M).db
```

## Observability

- Request logs are emitted in structured JSON and include `method`, `path`, `status`, `duration_ms`, and `request_id`.
- `X-Request-ID` is echoed when provided, or generated automatically.
- `GET /health` and `GET /ready` remain available.
- `GET /api/system` returns safe runtime info:
  - `db_path`, `db_exists`, `db_size_bytes`
  - `uptime_seconds`
  - `app_version`

## Troubleshooting checklist

- **DB permissions:** verify the mounted `/data` directory exists and is writable by the container UID/GID.
- **DB path:** confirm `KIDTUBE_DB_PATH` points to a writable location.
- **Traefik target port:** ensure reverse proxy forwards to container port `2018` (or your configured `PORT`).
- **Health check:** test `GET /health` through Traefik route and directly on container network.

## How Kid Selector Works

1. Kid opens dashboard and taps a kid card.
2. If profile has no pending PIN challenge, feed loads immediately.
3. If PIN is required, the PIN gate appears with numeric input.
4. On success, profile session is set and feed/category filtering unlocks.
5. If blocked by schedule/bedtime/limits, video APIs return explicit 403 reasons (`Outside allowed schedule`, `Within bedtime window`, `Daily watch limit reached`).

## Parent Controls

All parent controls are under `/admin`.

- **Channels + Categories** (`/admin/channels`)
  - Category CRUD (create, enable/disable)
  - Channel lookup, allow/enable/block toggles
- **Kid Controls** (`/admin/kids`)
  - Global daily limit + bedtime windows
  - Per-category daily overrides
  - Schedule windows by day of week
  - Bonus time (minutes + expiry)
- **Logs + Stats** (`/admin/stats`)
  - Today/lifetime totals
  - Stats by category
  - Recent watch and search logs

## Discord Setup

Discord integration is used to validate interaction payloads and post approval notifications.

Required env vars:

- `DISCORD_PUBLIC_KEY`
- `DISCORD_APPROVAL_WEBHOOK_URL`

Verification checklist:

1. Start app with env vars set.
2. Send a signed request to `POST /discord/interactions`.
3. Confirm valid requests return success and invalid signatures return `401`.
4. Trigger an approval flow and confirm webhook message appears in Discord.

## Security Notes

- **YouTube embeds:** the watch player uses `https://www.youtube-nocookie.com/embed/...`.
- **CSP headers:** UI responses set CSP in `app/ui.py`; frame sources are restricted to `youtube-nocookie`, while scripts/styles stay self-hosted (plus YouTube iframe API script).
- **Container user:** Docker image is non-root and writes only to writable paths (`/data`, `app/static/uploads`).

## New Phase 12 APIs

- `GET /api/search?q=...&kid_id=...` searches YouTube videos for kids, logs the query, and returns `duration_seconds` + `is_short` when available.
- `GET /api/channels/allowed?kid_id=...` returns globally allowed channels.
- `GET /api/channels/youtube/{channel_id}` returns kid-facing channel metadata for the channel page header.
- `GET /api/channels/{channel_id}/videos?kid_id=...` returns latest videos for a channel and enforces kid schedule/bedtime when `kid_id` is provided.
- `GET /api/logs/recent?kid_id=&limit=` returns joined watch logs including `kid_name`, channel/category names, and watched duration.
- `PUT /api/kids/{kid_id}/pin` and `DELETE /api/kids/{kid_id}/pin` set/remove kid PINs. PINs are stored as SHA-256 hashes with app secret salt.
- `GET /api/feed/shorts?kid_id=...` returns short-form feed rows, controlled by `parent_settings.shorts_enabled` and kid schedule checks.
- `GET /api/feed/latest-per-channel?kid_id=...` returns one latest item per allowed channel with optional kid schedule checks.
- `POST /api/playback/watch/log` accepts heartbeat watch deltas (`kid_id`, `video_id`, `seconds_delta`) for reliable watch logging during playback.
