from sqlalchemy import text
from sqlmodel import Session

from fastapi import APIRouter, Depends

from app.db.session import get_session

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(get_session)) -> dict[str, bool]:
    session.exec(text("SELECT 1")).first()
    return {"ready": True}
