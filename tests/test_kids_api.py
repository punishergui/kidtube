from pathlib import Path

from fastapi.testclient import TestClient
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


def test_create_kid_accepts_parent_controls(tmp_path: Path) -> None:
    db_path = tmp_path / 'kids-create-api.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    payload = {
        'name': 'Luna',
        'daily_limit_minutes': 50,
        'bedtime_start': '20:30',
        'bedtime_end': '06:30',
        'weekend_bonus_minutes': 20,
        'require_parent_approval': True,
    }

    try:
        with _client_for_engine(engine) as client:
            response = client.post('/api/kids', json=payload)
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 201
    created = response.json()
    assert created['name'] == 'Luna'
    assert created['bedtime_start'] == '20:30'
    assert created['bedtime_end'] == '06:30'
    assert created['weekend_bonus_minutes'] == 20
    assert created['require_parent_approval'] is True


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
            response = client.patch(
                f'/api/kids/{kid_id}',
                json={
                    'daily_limit_minutes': 45,
                    'bedtime_start': '21:00',
                    'bedtime_end': '07:00',
                    'weekend_bonus_minutes': 15,
                    'require_parent_approval': True,
                },
            )
            upload_response = client.post(
                f'/api/kids/{kid_id}/avatar',
                files={'file': ('avatar.png', b'\x89PNG\r\n\x1a\n', 'image/png')},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json()['daily_limit_minutes'] == 45
    assert response.json()['bedtime_start'] == '21:00'
    assert response.json()['bedtime_end'] == '07:00'
    assert response.json()['weekend_bonus_minutes'] == 15
    assert response.json()['require_parent_approval'] is True

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


def test_create_kid_rejects_invalid_bedtime(tmp_path: Path) -> None:
    db_path = tmp_path / 'kids-invalid-bedtime.db'
    engine = create_engine(f'sqlite:///{db_path}')
    run_migrations(engine, Path('app/db/migrations'))

    try:
        with _client_for_engine(engine) as client:
            response = client.post(
                '/api/kids',
                json={'name': 'Noah', 'bedtime_start': '8pm', 'bedtime_end': '06:00'},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 422
