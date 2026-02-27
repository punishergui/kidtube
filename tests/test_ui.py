from fastapi.testclient import TestClient

from app.main import app


def test_ui_root_renders_kidtube() -> None:
    with TestClient(app) as client:
        response = client.get('/')

    assert response.status_code == 200
    assert 'KidTube' in response.text


def test_static_asset_is_served() -> None:
    with TestClient(app) as client:
        response = client.get('/static/styles.css')

    assert response.status_code == 200
    assert 'app-shell' in response.text
