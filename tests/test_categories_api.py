from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Category
from app.db.session import get_session
from app.main import app


def _client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


def test_categories_crud(tmp_path: Path) -> None:
    db_path = tmp_path / "categories-api.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    try:
        with _client_for_engine(engine) as client:
            create_response = client.post(
                "/api/categories",
                json={"name": "Science", "daily_limit_minutes": 45},
            )
            list_response = client.get("/api/categories")

            category_id = create_response.json()["id"]
            patch_response = client.patch(
                f"/api/categories/{category_id}",
                json={"name": "STEM", "daily_limit_minutes": 50},
            )
            delete_response = client.delete(f"/api/categories/{category_id}")
            list_including_disabled = client.get("/api/categories?include_disabled=true")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["name"] == "Science"
    assert created_payload["enabled"] is True
    assert created_payload["daily_limit_minutes"] == 45

    assert list_response.status_code == 200
    listed_categories = list_response.json()
    assert {category["name"] for category in listed_categories} == {"education", "fun", "Science"}

    assert patch_response.status_code == 200
    patched_payload = patch_response.json()
    assert patched_payload["name"] == "STEM"
    assert patched_payload["daily_limit_minutes"] == 50

    assert delete_response.status_code == 200
    disabled_payload = delete_response.json()
    assert disabled_payload["enabled"] is False

    assert list_including_disabled.status_code == 200
    categories_with_disabled = list_including_disabled.json()
    assert any(
        category["id"] == category_id and category["enabled"] is False
        for category in categories_with_disabled
    )


def test_category_name_must_be_unique(tmp_path: Path) -> None:
    db_path = tmp_path / "categories-api-unique.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        music = Category(name="Music")
        art = Category(name="Art")
        session.add(music)
        session.add(art)
        session.commit()
        session.refresh(music)
        session.refresh(art)
        music_id = music.id
        art_id = art.id

    try:
        with _client_for_engine(engine) as client:
            duplicate_create_response = client.post("/api/categories", json={"name": "Music"})
            duplicate_patch_response = client.patch(
                f"/api/categories/{music_id}",
                json={"name": "Music"},
            )
            conflict_patch_response = client.patch(
                f"/api/categories/{art_id}",
                json={"name": "Music"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert duplicate_create_response.status_code == 409
    assert duplicate_patch_response.status_code == 200
    assert conflict_patch_response.status_code == 409


def test_category_daily_limit_minutes_validation(tmp_path: Path) -> None:
    db_path = tmp_path / "categories-api-validation.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    try:
        with _client_for_engine(engine) as client:
            invalid_create_response = client.post(
                "/api/categories",
                json={"name": "Games", "daily_limit_minutes": -1},
            )
            create_response = client.post("/api/categories", json={"name": "Games"})
            category_id = create_response.json()["id"]
            invalid_patch_response = client.patch(
                f"/api/categories/{category_id}",
                json={"daily_limit_minutes": -2},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert invalid_create_response.status_code == 422
    assert create_response.status_code == 201
    assert create_response.json()["enabled"] is True
    assert invalid_patch_response.status_code == 422


def test_category_name_cannot_be_blank(tmp_path: Path) -> None:
    db_path = tmp_path / "categories-api-blank.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    try:
        with _client_for_engine(engine) as client:
            invalid_create_response = client.post("/api/categories", json={"name": "   "})
            create_response = client.post("/api/categories", json={"name": "Science"})
            category_id = create_response.json()["id"]
            invalid_patch_response = client.patch(
                f"/api/categories/{category_id}",
                json={"name": ""},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert invalid_create_response.status_code == 400
    assert invalid_create_response.json()["detail"] == "Category name cannot be blank"
    assert invalid_patch_response.status_code == 422
