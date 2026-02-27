from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
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
