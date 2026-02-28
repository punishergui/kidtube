from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.api.routes_discord import router as discord_router
from app.api.routes_health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.request_context import request_logging_middleware
from app.core.version import get_version_payload
from app.db.migrate import run_migrations
from app.db.paths import ensure_db_parent_writable
from app.db.session import engine
from app.services.sync import periodic_sync
from app.ui import router as ui_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    sqlite_path = settings.sqlite_path
    if sqlite_path:
        try:
            ensure_db_parent_writable(sqlite_path)
        except Exception as exc:
            logger.error("database startup check failed", extra={"error": str(exc)})
            raise RuntimeError(str(exc)) from exc

    run_migrations(engine, Path(__file__).parent / "db" / "migrations")
    app.state.started_at = time.time()

    stop_event = asyncio.Event()
    sync_task: asyncio.Task[None] | None = None
    if settings.sync_enabled:
        sync_task = asyncio.create_task(periodic_sync(stop_event))

    try:
        yield
    finally:
        stop_event.set()
        if sync_task:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.middleware("http")(request_logging_middleware)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(health_router)
app.include_router(api_router)
app.include_router(discord_router)
app.include_router(ui_router)


@app.get("/version")
def version() -> dict[str, str | None]:
    return get_version_payload()
