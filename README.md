# KidTube

Minimal FastAPI service prepared for Docker publishing to GitHub Container Registry (GHCR).

## Endpoints

- `GET /health` → `{"ok": true}`
- `GET /` → HTML page with `KidTube running`

## Run locally (Python)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 2018
```

## Run with Docker

```bash
docker build -t kidtube:local .
docker run --rm -p 2018:2018 kidtube:local
```

## Test with curl

```bash
curl http://localhost:2018/health
curl http://localhost:2018/
```

## GitHub Actions publish

On every push to `main`, workflow `.github/workflows/docker-publish.yml` builds and pushes:

- `ghcr.io/punishergui/kidtube:latest`
- `ghcr.io/punishergui/kidtube:main`
