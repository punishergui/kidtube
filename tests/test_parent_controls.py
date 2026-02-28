from datetime import datetime, time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from sqlmodel import select

from app.db.models import Category, Channel, Kid, KidSchedule, Video
from app.db.session import get_session
from app.main import app


def _client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


def test_pin_gate_and_kid_session_cookie(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'pin.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Mia', pin_hash='1234')
        session.add(kid)
        session.commit()
        session.refresh(kid)

    try:
        with _client_for_engine(engine) as client:
            pending = client.post('/api/session/kid', json={'kid_id': kid.id})
            assert pending.status_code == 200
            assert pending.json()['pin_required'] is True

            bad = client.post('/api/session/kid/verify-pin', json={'pin': '0000'})
            assert bad.status_code == 403

            ok = client.post('/api/session/kid/verify-pin', json={'pin': '1234'})
            assert ok.status_code == 200
            assert ok.json()['kid_id'] == kid.id

            status_resp = client.get('/api/session/kid')
            assert status_resp.json()['kid_id'] == kid.id
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_playback_enforces_schedule(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'schedule.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        category = session.exec(select(Category).where(Category.name == 'fun')).first()
        category_id = category.id if category else None
        kid = Kid(name='Noah', daily_limit_minutes=60)
        session.add(kid)
        session.commit()
        session.refresh(kid)
        session.add(KidSchedule(kid_id=kid.id, day_of_week=datetime.utcnow().weekday(), start_time=time(0, 0, 0), end_time=time(0, 0, 1)))

        channel = Channel(youtube_id='chan1', title='Test', allowed=True, blocked=False, enabled=True, category='fun', category_id=category_id)
        session.add(channel)
        session.commit()
        session.refresh(channel)

        session.add(Video(youtube_id='vid1', channel_id=channel.id, title='Video', thumbnail_url='http://x', published_at=datetime.utcnow()))
        session.commit()

    try:
        with _client_for_engine(engine) as client:
            client.post('/api/session/kid', json={'kid_id': kid.id})
            resp = client.get('/api/videos/vid1')
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_kids_api_returns_avatar_and_pin_flag(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'avatar.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Ava', pin_hash='9999')
        session.add(kid)
        session.commit()

    try:
        with _client_for_engine(engine) as client:
            response = client.get('/api/kids')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json()[0]['has_pin'] is True
