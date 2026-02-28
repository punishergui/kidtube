import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(get_session)) -> dict[str, bool]:
    session.exec(text("SELECT 1")).first()
    return {"ready": True}


@router.get("/api/system")
def system_details(request: Request) -> dict[str, int | bool | str | None]:
    db_path = settings.sqlite_path
    db_exists = bool(db_path and db_path.exists())
    db_size_bytes = db_path.stat().st_size if db_path and db_path.exists() else 0
    started_at = getattr(request.app.state, "started_at", None)
    uptime_seconds = int(time.time() - started_at) if started_at else 0

    sanitized_db_path = None
    if db_path:
        sanitized_db_path = str(Path(db_path).expanduser())

    return {
        "db_path": sanitized_db_path,
        "db_exists": db_exists,
        "db_size_bytes": db_size_bytes,
        "uptime_seconds": uptime_seconds,
        "app_version": settings.app_version,
    }
