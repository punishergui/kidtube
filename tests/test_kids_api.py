from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Kid
from app.db.session import get_session
from app.main import app


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

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        with TestClient(app) as client:
            response = client.patch(f'/api/kids/{kid_id}', json={'daily_limit_minutes': 45})
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json()['daily_limit_minutes'] == 45
