from pathlib import Path

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

    assert response.history[0].status_code == 307
    assert str(response.url).endswith('/')


def test_admin_pages_render() -> None:
    with TestClient(app) as client:
        admin = client.get('/admin')
        channels = client.get('/admin/channels')
        kids = client.get('/admin/kids')
        sync = client.get('/admin/sync')
        stats = client.get('/admin/stats')

    assert admin.status_code == 200
    assert channels.status_code == 200
    assert kids.status_code == 200
    assert sync.status_code == 200
    assert stats.status_code == 200


def test_static_asset_is_served() -> None:
    with TestClient(app) as client:
        response = client.get('/static/styles.css')

    assert response.status_code == 200
    assert 'app-shell' in response.text


def test_ui_sets_csp_to_youtube_nocookie_only() -> None:
    with TestClient(app) as client:
        response = client.get('/watch/fake-video-id')

    csp = response.headers['content-security-policy']
    assert 'frame-src https://www.youtube-nocookie.com' in csp
    assert 'youtube.com/embed' not in csp


def test_watch_js_uses_youtube_nocookie_embed() -> None:
    watch_js = Path("app/static/watch.js").read_text()
    assert "youtube-nocookie.com/embed" in watch_js
    assert "youtube.com/embed" not in watch_js
