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
| `DATABASE_URL` | `sqlite:////data/kidtube.db` | SQLite path |
| `SECRET_KEY` | *(required in production)* | Session signing |
| `YOUTUBE_API_KEY` | *(empty)* | Channel lookup + sync |
| `DISCORD_PUBLIC_KEY` | *(empty)* | Discord signature verification |
| `DISCORD_APPROVAL_WEBHOOK_URL` | *(empty)* | Post approval events to Discord |
| `KIDTUBE_SYNC_ENABLED` | `true` | Background sync on/off |
| `KIDTUBE_SYNC_INTERVAL_SECONDS` | `900` | Background sync interval |
| `SYNC_MAX_VIDEOS_PER_CHANNEL` | `15` | Max videos/channel per sync |

## Docker (non-root)

The image runs as non-root user `kidtube` (UID/GID defaults to `10001`).

```bash
docker build -t kidtube .
docker run --rm -p 2018:2018 \
  -e DATABASE_URL=sqlite:////data/kidtube.db \
  -v "$(pwd)/data:/data" \
  kidtube
```

If host volume permissions are strict, align IDs:

```bash
docker build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g) -t kidtube .
```

Make sure mounted `/data` is writable by the container user.

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
