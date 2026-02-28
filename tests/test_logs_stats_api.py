from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Category, Channel, Kid, Video
from app.db.session import get_session
from app.main import app


def _client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


def test_search_log_write_and_list(tmp_path: Path) -> None:
    db_path = tmp_path / 'logs-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Mia')
        session.add(kid)
        session.commit()
        session.refresh(kid)
        kid_id = kid.id

    try:
        with _client_for_engine(engine) as client:
            create_response = client.post(
                '/api/logs/search',
                json={'kid_id': kid_id, 'query': 'cats'},
            )
            list_response = client.get('/api/logs/search', params={'kid_id': kid_id, 'limit': 5})
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert create_response.status_code == 201
    assert create_response.json() == {'ok': True}
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]['kid_id'] == kid_id
    assert rows[0]['query'] == 'cats'


def test_stats_returns_category_aggregates(tmp_path: Path) -> None:
    db_path = tmp_path / 'stats-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    now = datetime.now(timezone.utc)  # noqa: UP017
    today_value = now.isoformat()
    yesterday_value = (now - timedelta(days=1)).isoformat()

    with Session(engine) as session:
        kid = Kid(name='Noah')
        category = session.execute(
            text(
                """
                SELECT id
                FROM categories
                WHERE name = 'education'
                LIMIT 1
                """
            )
        ).mappings().first()
        category_id: int | None = int(category['id']) if category else None
        if category_id is None:
            category_model = Category(name='education')
            session.add(category_model)
            session.flush()
            category_id = category_model.id

        channel = Channel(
            youtube_id='chan-1',
            title='Ch',
            allowed=True,
            enabled=True,
            blocked=False,
            category_id=category_id,
        )
        session.add(kid)
        session.add(channel)
        session.commit()
        session.refresh(kid)
        session.refresh(channel)

        video = Video(
            youtube_id='vid-1',
            channel_id=channel.id,
            title='Video',
            thumbnail_url='https://example.com/t.jpg',
            published_at=now,
        )
        session.add(video)
        session.commit()
        session.refresh(video)

        session.execute(
            text(
                """
                INSERT INTO watch_log(kid_id, video_id, seconds_watched, category_id, created_at)
                VALUES (:kid_id, :video_id, 40, :category_id, :created_at)
                """
            ),
            {
                'kid_id': kid.id,
                'video_id': video.id,
                'category_id': category_id,
                'created_at': today_value,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO watch_log(kid_id, video_id, seconds_watched, category_id, created_at)
                VALUES (:kid_id, :video_id, 80, :category_id, :created_at)
                """
            ),
            {
                'kid_id': kid.id,
                'video_id': video.id,
                'category_id': category_id,
                'created_at': yesterday_value,
            },
        )
        session.commit()
        kid_id = kid.id

    try:
        with _client_for_engine(engine) as client:
            response = client.get('/api/stats', params={'kid_id': kid_id})
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload['kid_id'] == kid_id
    assert payload['today_seconds'] == 40
    assert payload['lifetime_seconds'] == 120
    assert len(payload['categories']) == 1
    assert payload['categories'][0]['category_name'] == 'education'
    assert payload['categories'][0]['today_seconds'] == 40
    assert payload['categories'][0]['lifetime_seconds'] == 120
