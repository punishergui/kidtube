from __future__ import annotations

import asyncio

import httpx

from app.core.config import settings
from app.services.youtube import parse_channel_input, resolve_channel


def test_parse_direct_channel_id_url() -> None:
    parsed = parse_channel_input("https://www.youtube.com/channel/UC1234567890123456789012")
    assert parsed.channel_id == "UC1234567890123456789012"


def test_parse_handle_input() -> None:
    parsed = parse_channel_input("@SciShowKids")
    assert parsed.handle == "SciShowKids"


def test_resolve_handle_with_mock_transport(monkeypatch) -> None:
    monkeypatch.setattr(settings, "youtube_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.url.path.endswith("/channels")
            and request.url.params.get("forHandle") == "SciShowKids"
        ):
            return httpx.Response(200, json={"items": [{"id": "UC1234567890123456789012"}]})
        if (
            request.url.path.endswith("/channels")
            and request.url.params.get("id") == "UC1234567890123456789012"
        ):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "UC1234567890123456789012",
                            "snippet": {
                                "title": "SciShow Kids",
                                "thumbnails": {"high": {"url": "https://img.example/avatar.jpg"}},
                            },
                            "brandingSettings": {
                                "image": {"bannerExternalUrl": "https://img.example/banner.jpg"}
                            },
                        }
                    ]
                },
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(resolve_channel("@SciShowKids", client=client))
    finally:
        asyncio.run(client.aclose())

    assert result["channel_id"] == "UC1234567890123456789012"
    assert result["title"] == "SciShow Kids"
