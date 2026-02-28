from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Channel, Kid, Video
from app.db.session import get_session
from app.main import app


def test_video_lookup_unknown_id_returns_404(tmp_path: Path) -> None:
    db_path = tmp_path / 'videos-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        with TestClient(app) as client:
            response = client.get('/api/videos/missing-video-id')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 404
    assert response.json() == {'detail': 'Video not found'}


def test_video_lookup_enforces_parent_approval_when_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / 'videos-approval-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    now = datetime.now(timezone.utc)  # noqa: UP017

    with Session(engine) as session:
        kid = Kid(name='Pia', require_parent_approval=True)
        channel = Channel(
            youtube_id='UCvideoapprove00000000000',
            title='Video Approval',
            resolve_status='ok',
            allowed=True,
        )
        session.add(kid)
        session.add(channel)
        session.commit()
        session.refresh(kid)
        session.refresh(channel)

        video = Video(
            youtube_id='vid-parent-gate',
            channel_id=channel.id,
            title='Guarded',
            thumbnail_url='https://img.example/guarded.jpg',
            published_at=now,
        )
        session.add(video)
        session.commit()

        kid_id = kid.id

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        with TestClient(app) as client:
            blocked = client.get(f'/api/videos/vid-parent-gate?kid_id={kid_id}')

            with Session(engine) as session:
                session.exec(
                    text(
                        """
                        INSERT INTO requests (type, youtube_id, kid_id, status)
                        VALUES ('video', 'vid-parent-gate', :kid_id, 'approved')
                        """
                    ),
                    {'kid_id': kid_id},
                )
                session.commit()

            allowed = client.get(f'/api/videos/vid-parent-gate?kid_id={kid_id}')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert blocked.status_code == 403
    assert blocked.json() == {'detail': 'Parent approval required for this video'}

    assert allowed.status_code == 200
    assert allowed.json()['youtube_id'] == 'vid-parent-gate'
