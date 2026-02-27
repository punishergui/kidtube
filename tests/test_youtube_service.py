from __future__ import annotations

import asyncio

import httpx

from app.core.config import settings
from app.services.youtube import parse_channel_input, resolve_channel, resolve_handle_to_channel_id

CHANNEL_ID = "UC1234567890123456789012"


def test_parse_direct_channel_id_url() -> None:
    parsed = parse_channel_input(f"https://www.youtube.com/channel/{CHANNEL_ID}")
    assert parsed.channel_id == CHANNEL_ID


def test_parse_channel_id_url_without_www() -> None:
    parsed = parse_channel_input(f"https://youtube.com/channel/{CHANNEL_ID}")
    assert parsed.channel_id == CHANNEL_ID


def test_parse_handle_input() -> None:
    parsed = parse_channel_input("@SciShowKids")
    assert parsed.handle == "SciShowKids"


def test_parse_handle_url_with_www() -> None:
    parsed = parse_channel_input("https://www.youtube.com/@SciShowKids")
    assert parsed.handle == "SciShowKids"


def test_parse_handle_url_without_www() -> None:
    parsed = parse_channel_input("https://youtube.com/@SciShowKids")
    assert parsed.handle == "SciShowKids"


def test_resolve_handle_with_mock_transport(monkeypatch) -> None:
    monkeypatch.setattr(settings, "youtube_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.url.path.endswith("/channels")
            and request.url.params.get("forHandle") == "SciShowKids"
        ):
            return httpx.Response(200, json={"items": [{"id": CHANNEL_ID}]})
        if request.url.path.endswith("/channels") and request.url.params.get("id") == CHANNEL_ID:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": CHANNEL_ID,
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

    assert result["channel_id"] == CHANNEL_ID
    assert result["title"] == "SciShow Kids"


def test_resolve_handle_falls_back_to_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json={"items": []})
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {
                                "channelId": CHANNEL_ID,
                                "channelTitle": "NationalGeographicKids",
                            }
                        }
                    ]
                },
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        resolved = asyncio.run(
            resolve_handle_to_channel_id("NationalGeographicKids", "test-key", client=client)
        )
    finally:
        asyncio.run(client.aclose())

    assert resolved == CHANNEL_ID
