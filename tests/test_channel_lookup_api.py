from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_channel_lookup_unknown_handle_returns_not_found(monkeypatch) -> None:
    async def fake_resolve_channel(_query: str) -> dict[str, str | None]:
        raise RuntimeError('Unable to resolve handle')

    monkeypatch.setattr('app.api.routes_channel_lookup.resolve_channel', fake_resolve_channel)

    with TestClient(app) as client:
        response = client.get('/api/channel-lookup', params={'query': '@unknown'})

    assert response.status_code == 200
    assert response.json() == {
        'query': '@unknown',
        'found': False,
        'channel': None,
        'sample_videos': [],
        'error': 'Unable to resolve handle',
    }


def test_channel_lookup_known_handle_returns_preview(monkeypatch) -> None:
    async def fake_resolve_channel(_query: str) -> dict[str, str | int | None]:
        return {
            'channel_id': 'UC1234567890123456789012',
            'title': 'SciShow Kids',
            'handle': '@SciShowKids',
            'avatar_url': 'https://img.example/avatar.jpg',
            'banner_url': 'https://img.example/banner.jpg',
            'description': 'Science videos for children',
            'subscriber_count': 42,
            'video_count': 8,
        }

    async def fake_fetch_latest_videos(_channel_id: str, max_results: int = 10) -> list[dict[str, str]]:
        assert max_results == 6
        return [
            {
                'youtube_id': 'abc123def45',
                'title': 'Atoms for Kids',
                'thumbnail_url': 'https://i.ytimg.com/vi/abc123def45/hqdefault.jpg',
                'published_at': '2024-01-02T00:00:00Z',
            }
        ]

    monkeypatch.setattr('app.api.routes_channel_lookup.resolve_channel', fake_resolve_channel)
    monkeypatch.setattr('app.api.routes_channel_lookup.fetch_latest_videos', fake_fetch_latest_videos)

    with TestClient(app) as client:
        response = client.get('/api/channel-lookup', params={'query': '@SciShowKids'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['found'] is True
    assert payload['error'] is None
    assert payload['channel']['youtube_id'] == 'UC1234567890123456789012'
    assert payload['channel']['handle'] == '@SciShowKids'
    assert payload['sample_videos'][0]['youtube_id'] == 'abc123def45'
