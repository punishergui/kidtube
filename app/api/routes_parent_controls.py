from __future__ import annotations

from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.models import (
    Category,
    Kid,
    KidBonusTime,
    KidCategoryLimit,
    KidSchedule,
    Request as ApprovalRequest,
    SearchLog,
    Video,
    WatchLog,
)
from app.db.session import get_session
from app.services.parent_controls import assert_playback_allowed

router = APIRouter()


class SessionStatus(BaseModel):
    kid_id: int | None
    pin_required: bool = False


class SelectKidPayload(BaseModel):
    kid_id: int


class VerifyPinPayload(BaseModel):
    pin: str


class CategoryPayload(BaseModel):
    name: str
    enabled: bool = True
    daily_limit_minutes: int | None = None


class CategoryRead(CategoryPayload):
    id: int


class KidLimitPayload(BaseModel):
    category_id: int
    daily_limit_minutes: int


class SchedulePayload(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str


class BonusPayload(BaseModel):
    minutes: int
    expires_at: datetime | None = None


class PlaybackPayload(BaseModel):
    video_youtube_id: str
    watched_seconds: int


class SearchPayload(BaseModel):
    query: str


@router.get('/session/kid', response_model=SessionStatus)
def get_kid_session(request: Request) -> SessionStatus:
    return SessionStatus(
        kid_id=request.session.get('kid_id'),
        pin_required=bool(request.session.get('pending_kid_id')),
    )


@router.post('/session/kid', response_model=SessionStatus)
def select_kid(payload: SelectKidPayload, request: Request, session: Session = Depends(get_session)) -> SessionStatus:
    kid = session.get(Kid, payload.kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail='Kid not found')

    request.session.pop('kid_id', None)
    request.session.pop('pending_kid_id', None)
    if kid.pin_hash:
        request.session['pending_kid_id'] = kid.id
        return SessionStatus(kid_id=None, pin_required=True)

    request.session['kid_id'] = kid.id
    return SessionStatus(kid_id=kid.id, pin_required=False)


@router.post('/session/kid/verify-pin', response_model=SessionStatus)
def verify_kid_pin(payload: VerifyPinPayload, request: Request, session: Session = Depends(get_session)) -> SessionStatus:
    pending_id = request.session.get('pending_kid_id')
    if not pending_id:
        raise HTTPException(status_code=400, detail='No pending PIN challenge')
    kid = session.get(Kid, pending_id)
    if not kid or kid.pin_hash != payload.pin:
        raise HTTPException(status_code=403, detail='Invalid PIN')

    request.session.pop('pending_kid_id', None)
    request.session['kid_id'] = kid.id
    return SessionStatus(kid_id=kid.id, pin_required=False)


@router.delete('/session/kid', status_code=status.HTTP_204_NO_CONTENT)
def clear_kid_session(request: Request) -> None:
    request.session.pop('kid_id', None)
    request.session.pop('pending_kid_id', None)


@router.get('/categories', response_model=list[CategoryRead])
def list_categories(session: Session = Depends(get_session)) -> list[Category]:
    return session.exec(select(Category).order_by(Category.name)).all()


@router.post('/categories', response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryPayload, session: Session = Depends(get_session)) -> Category:
    category = Category.model_validate(payload)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.patch('/categories/{category_id}', response_model=CategoryRead)
def patch_category(category_id: int, payload: CategoryPayload, session: Session = Depends(get_session)) -> Category:
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    for field, value in payload.model_dump().items():
        setattr(category, field, value)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete('/categories/{category_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, session: Session = Depends(get_session)) -> None:
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    session.delete(category)
    session.commit()


@router.post('/kids/{kid_id}/limits', status_code=status.HTTP_201_CREATED)
def upsert_kid_limit(kid_id: int, payload: KidLimitPayload, session: Session = Depends(get_session)) -> KidCategoryLimit:
    record = session.exec(
        select(KidCategoryLimit).where(
            KidCategoryLimit.kid_id == kid_id,
            KidCategoryLimit.category_id == payload.category_id,
        )
    ).first()
    if record:
        record.daily_limit_minutes = payload.daily_limit_minutes
    else:
        record = KidCategoryLimit(kid_id=kid_id, **payload.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.post('/kids/{kid_id}/schedules', status_code=status.HTTP_201_CREATED)
def add_schedule(kid_id: int, payload: SchedulePayload, session: Session = Depends(get_session)) -> KidSchedule:
    schedule = KidSchedule(
        kid_id=kid_id,
        day_of_week=payload.day_of_week,
        start_time=time.fromisoformat(payload.start_time),
        end_time=time.fromisoformat(payload.end_time),
    )
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.post('/kids/{kid_id}/bonus-time', status_code=status.HTTP_201_CREATED)
def grant_bonus_time(kid_id: int, payload: BonusPayload, session: Session = Depends(get_session)) -> KidBonusTime:
    expires_at = payload.expires_at or datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)
    grant = KidBonusTime(kid_id=kid_id, minutes=payload.minutes, expires_at=expires_at)
    session.add(grant)
    session.commit()
    session.refresh(grant)
    return grant


@router.post('/logs/search', status_code=status.HTTP_201_CREATED)
def create_search_log(payload: SearchPayload, request: Request, session: Session = Depends(get_session)) -> SearchLog:
    kid_id = request.session.get('kid_id')
    if not kid_id:
        raise HTTPException(status_code=403, detail='Kid session is required')
    row = SearchLog(kid_id=kid_id, query=payload.query)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.post('/playback/log', status_code=status.HTTP_201_CREATED)
def log_playback(payload: PlaybackPayload, request: Request, session: Session = Depends(get_session)) -> WatchLog:
    kid_id = request.session.get('kid_id')
    if not kid_id:
        raise HTTPException(status_code=403, detail='Kid session is required')

    video = session.exec(select(Video).where(Video.youtube_id == payload.video_youtube_id)).first()
    if not video:
        raise HTTPException(status_code=404, detail='Video not found')
    assert_playback_allowed(session, kid_id, video)

    log = WatchLog(kid_id=kid_id, video_id=video.id, watched_seconds=payload.watched_seconds)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@router.get('/parent/logs')
def parent_logs(session: Session = Depends(get_session)) -> dict[str, list[dict[str, str | int]]]:
    watches = session.exec(select(WatchLog).order_by(WatchLog.watched_at.desc())).all()
    searches = session.exec(select(SearchLog).order_by(SearchLog.searched_at.desc())).all()
    return {
        'watches': [w.model_dump() for w in watches],
        'searches': [s.model_dump() for s in searches],
    }


@router.get('/parent/stats')
def parent_stats(session: Session = Depends(get_session)) -> dict[str, int]:
    watches = session.exec(select(WatchLog)).all()
    total_watch_seconds = sum(w.watched_seconds for w in watches)
    total_searches = len(session.exec(select(SearchLog)).all())
    return {
        'total_watch_seconds': total_watch_seconds,
        'total_searches': total_searches,
    }


@router.post('/requests/channel/{channel_youtube_id}', status_code=status.HTTP_201_CREATED)
def request_channel(channel_youtube_id: str, request: Request, session: Session = Depends(get_session)) -> ApprovalRequest:
    row = ApprovalRequest(type='channel', youtube_id=channel_youtube_id, kid_id=request.session.get('kid_id'))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.post('/requests/video/{video_youtube_id}', status_code=status.HTTP_201_CREATED)
def request_video(video_youtube_id: str, request: Request, session: Session = Depends(get_session)) -> ApprovalRequest:
    row = ApprovalRequest(type='video', youtube_id=video_youtube_id, kid_id=request.session.get('kid_id'))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.post('/discord/actions/grant-bonus/{kid_id}/{minutes}')
def discord_grant_bonus(kid_id: int, minutes: int, session: Session = Depends(get_session)) -> dict[str, str]:
    expires_at = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)
    if minutes <= 0:
        raise HTTPException(status_code=400, detail='Invalid bonus amount')
    if minutes >= 24 * 60:
        expires_at = datetime.utcnow() + timedelta(days=1)
    grant = KidBonusTime(kid_id=kid_id, minutes=minutes, expires_at=expires_at)
    session.add(grant)
    session.commit()
    return {'status': 'granted'}
