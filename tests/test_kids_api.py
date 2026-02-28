from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Kid
from app.db.session import get_session
from app.main import app


def _client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


def test_patch_kid_updates_daily_limit_minutes(tmp_path: Path) -> None:
    db_path = tmp_path / 'kids-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Ava', daily_limit_minutes=30)
        session.add(kid)
        session.commit()
        session.refresh(kid)
        kid_id = kid.id

    app_root = Path(__file__).resolve().parents[1]
    avatar_file = app_root / 'app' / 'static' / 'uploads' / 'kids' / str(kid_id) / 'avatar.png'

    try:
        with _client_for_engine(engine) as client:
            response = client.patch(f'/api/kids/{kid_id}', json={'daily_limit_minutes': 45})
            upload_response = client.post(
                f'/api/kids/{kid_id}/avatar',
                files={'file': ('avatar.png', b'\x89PNG\r\n\x1a\n', 'image/png')},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json()['daily_limit_minutes'] == 45

    assert upload_response.status_code == 200
    avatar_url = upload_response.json()['avatar_url']
    assert avatar_url.startswith(f'/static/uploads/kids/{kid_id}/avatar.png?v=')
    assert avatar_file.exists()

    try:
        with _client_for_engine(engine) as client:
            delete_avatar_response = client.delete(f'/api/kids/{kid_id}/avatar')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert delete_avatar_response.status_code == 200
    assert delete_avatar_response.json()['avatar_url'] is None
    assert not avatar_file.exists()



def test_bonus_time_endpoints_create_and_list_active_grants(tmp_path: Path) -> None:
    db_path = tmp_path / 'kids-bonus-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Liam', daily_limit_minutes=10)
        session.add(kid)
        session.commit()
        session.refresh(kid)
        kid_id = kid.id

    try:
        with _client_for_engine(engine) as client:
            create_response = client.post(
                f'/api/kids/{kid_id}/bonus-time',
                json={'minutes': 15},
            )
            list_response = client.get(f'/api/kids/{kid_id}/bonus-time')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload['minutes'] == 15
    assert payload['expires_at'] is not None

    assert list_response.status_code == 200
    grants = list_response.json()
    assert len(grants) == 1
    assert grants[0]['minutes'] == 15



def test_bonus_time_list_only_returns_active_grants(tmp_path: Path) -> None:
    db_path = tmp_path / 'kids-bonus-active-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Zoe', daily_limit_minutes=10)
        session.add(kid)
        session.commit()
        session.refresh(kid)
        kid_id = kid.id
        session.execute(
            text(
                """
                INSERT INTO kid_bonus_time(kid_id, minutes, expires_at)
                VALUES (:kid_id, 5, '2000-01-01T00:00:00+00:00')
                """
            ),
            {'kid_id': kid_id},
        )
        session.execute(
            text(
                """
                INSERT INTO kid_bonus_time(kid_id, minutes, expires_at)
                VALUES (:kid_id, 7, '2999-01-01T00:00:00+00:00')
                """
            ),
            {'kid_id': kid_id},
        )
        session.commit()

    try:
        with _client_for_engine(engine) as client:
            list_response = client.get(f'/api/kids/{kid_id}/bonus-time')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert list_response.status_code == 200
    grants = list_response.json()
    assert len(grants) == 1
    assert grants[0]['minutes'] == 7
