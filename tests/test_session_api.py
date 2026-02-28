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


def test_select_kid_without_pin_sets_kid_id(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'session-no-pin.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Ava')
        session.add(kid)
        session.commit()
        session.refresh(kid)

    try:
        with _client_for_engine(engine) as client:
            response = client.post('/api/session/kid', json={'kid_id': kid.id})
            state = client.get('/api/session')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() == {'kid_id': kid.id, 'pin_required': False}
    assert state.json() == {'kid_id': kid.id, 'pending_kid_id': None}


def test_select_kid_with_pin_sets_pending_only(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'session-with-pin.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Ben', pin='1234')
        session.add(kid)
        session.commit()
        session.refresh(kid)

    try:
        with _client_for_engine(engine) as client:
            response = client.post('/api/session/kid', json={'kid_id': kid.id})
            state = client.get('/api/session')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() == {'kid_id': kid.id, 'pin_required': True}
    assert state.json() == {'kid_id': None, 'pending_kid_id': kid.id}


def test_verify_pin_wrong_returns_403(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'session-pin-wrong.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Casey', pin='7777')
        session.add(kid)
        session.commit()
        session.refresh(kid)

    try:
        with _client_for_engine(engine) as client:
            client.post('/api/session/kid', json={'kid_id': kid.id})
            response = client.post('/api/session/kid/verify-pin', json={'pin': '0000'})
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 403


def test_verify_pin_success_sets_kid_id_and_clears_pending(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'session-pin-ok.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Dee', pin='2468')
        session.add(kid)
        session.commit()
        session.refresh(kid)

    try:
        with _client_for_engine(engine) as client:
            client.post('/api/session/kid', json={'kid_id': kid.id})
            response = client.post('/api/session/kid/verify-pin', json={'pin': '2468'})
            state = client.get('/api/session')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() == {'kid_id': kid.id, 'ok': True}
    assert state.json() == {'kid_id': kid.id, 'pending_kid_id': None}


def test_logout_clears_session(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'session-logout.db'}")
    run_migrations(engine, Path('app/db/migrations'))

    with Session(engine) as session:
        kid = Kid(name='Eli')
        session.add(kid)
        session.commit()
        session.refresh(kid)

    try:
        with _client_for_engine(engine) as client:
            client.post('/api/session/kid', json={'kid_id': kid.id})
            response = client.post('/api/session/logout')
            state = client.get('/api/session')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() == {'ok': True}
    assert state.json() == {'kid_id': None, 'pending_kid_id': None}
