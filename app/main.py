from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.router import api_router
from app.api.routes_discord import router as discord_router
from app.api.routes_health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.version import get_version_payload
from app.db.migrate import run_migrations
from app.db.session import engine
from app.services.sync import periodic_sync


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging(settings.log_level)
    sqlite_path = settings.sqlite_path
    if sqlite_path:
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

    run_migrations(engine, Path(__file__).parent / "db" / "migrations")

    stop_event = asyncio.Event()
    sync_task = asyncio.create_task(periodic_sync(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await sync_task


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.include_router(health_router)
app.include_router(api_router)
app.include_router(discord_router)


@app.get("/version")
def version() -> dict[str, str | None]:
    return get_version_payload()
