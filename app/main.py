from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.api.routes_discord import router as discord_router
from app.api.routes_health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.request_context import request_logging_middleware
from app.core.version import get_version_payload
from app.db.migrate import run_migrations
from app.db.paths import ensure_db_parent_writable, format_dir_diagnostics
from app.db.session import engine
from app.services.daily_stats import send_daily_stats
from app.services.sync import periodic_sync
from app.ui import router as ui_router

logger = logging.getLogger(__name__)


async def periodic_daily_stats(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        now = datetime.now(UTC)
        next_run = now.replace(hour=settings.stats_hour % 24, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + timedelta(days=1)

        wait_seconds = max(1, int((next_run - now).total_seconds()))
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=wait_seconds)
            continue
        except TimeoutError:
            pass

        try:
            with Session(engine) as session:
                await send_daily_stats(session)
        except Exception as exc:
            logger.warning("Daily stats task failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    sqlite_path = settings.sqlite_path
    if sqlite_path:
        parent = sqlite_path.parent
        process_uid = os.getuid()
        process_gid = os.getgid()
        parent_info = format_dir_diagnostics(parent)
        try:
            ensure_db_parent_writable(sqlite_path)
        except Exception as exc:
            logger.error(
                (
                    "Database startup check failed: %s | resolved_sqlite_path=%s uid=%s gid=%s "
                    "parent=%s parent_owner_uid=%s parent_owner_gid=%s parent_mode=%s "
                    "parent_writable=%s"
                ),
                exc,
                sqlite_path,
                process_uid,
                process_gid,
                parent,
                parent_info.get("owner_uid"),
                parent_info.get("owner_gid"),
                parent_info.get("mode"),
                parent_info.get("writable"),
            )
            raise RuntimeError(str(exc)) from exc

    avatars_dir = Path("/data/avatars/kids")
    avatars_dir.mkdir(parents=True, exist_ok=True)

    run_migrations(engine, Path(__file__).parent / "db" / "migrations")
    app.state.started_at = time.time()

    stop_event = asyncio.Event()
    sync_task: asyncio.Task[None] | None = None
    daily_stats_task: asyncio.Task[None] | None = None
    if settings.sync_enabled:
        sync_task = asyncio.create_task(periodic_sync(stop_event))
    daily_stats_task = asyncio.create_task(periodic_daily_stats(stop_event))

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

        if daily_stats_task:
            daily_stats_task.cancel()
            try:
                await daily_stats_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.middleware("http")(request_logging_middleware)
app.mount(
    "/static/uploads/kids",
    StaticFiles(directory=Path("/data/avatars/kids")),
    name="kid-avatars",
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(health_router)
app.include_router(api_router)
app.include_router(discord_router)
app.include_router(ui_router)


@app.get("/version")
def version() -> dict[str, str | None]:
    return get_version_payload()
