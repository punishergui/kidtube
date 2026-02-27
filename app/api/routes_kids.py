from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.models import Kid
from app.db.session import get_session

router = APIRouter(prefix="/api/kids", tags=["kids"])


class KidCreate(BaseModel):
    name: str
    avatar_url: str | None = None
    daily_limit_minutes: int | None = None


class KidRead(BaseModel):
    id: int
    name: str
    avatar_url: str | None
    daily_limit_minutes: int | None
    created_at: datetime


@router.get("", response_model=list[KidRead])
def list_kids(session: Session = Depends(get_session)) -> list[Kid]:
    return session.exec(select(Kid).order_by(Kid.id)).all()


@router.post("", response_model=KidRead, status_code=status.HTTP_201_CREATED)
def create_kid(payload: KidCreate, session: Session = Depends(get_session)) -> Kid:
    kid = Kid.model_validate(payload)
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return kid
