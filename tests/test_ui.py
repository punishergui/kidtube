from fastapi.testclient import TestClient

from app.main import app


def test_ui_root_renders_kidtube() -> None:
    with TestClient(app) as client:
        response = client.get('/')

    assert response.status_code == 200
    assert 'KidTube' in response.text


def test_watch_page_renders_friendly_not_found_panel() -> None:
    with TestClient(app) as client:
        response = client.get('/watch/fake-video-id')

    assert response.status_code == 200
    assert 'Video not found' in response.text


def test_admin_pages_render() -> None:
    with TestClient(app) as client:
        admin = client.get('/admin')
        channels = client.get('/admin/channels')
        sync = client.get('/admin/sync')

    assert admin.status_code == 200
    assert channels.status_code == 200
    assert sync.status_code == 200


def test_static_asset_is_served() -> None:
    with TestClient(app) as client:
        response = client.get('/static/styles.css')

    assert response.status_code == 200
    assert 'app-shell' in response.text
