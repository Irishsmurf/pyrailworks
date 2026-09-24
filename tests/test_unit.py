"""Unit tests using mocked HTTP responses (offline and deterministic)."""
import pytest
import respx
import httpx
from pyrailworks import (
    RailworksClient,
    AsyncRailworksClient,
    BadRequestError,
    NotFoundError,
    StationsLoadingError,
    ProblemError,
    LineName,
    NoticeStatus,
)

BASE_URL = "https://railworks.paddez.com"


@pytest.fixture
def sync_client():
    with RailworksClient(base_url=BASE_URL) as client:
        yield client


@pytest.fixture
async def async_client():
    async with AsyncRailworksClient(base_url=BASE_URL) as client:
        yield client


@respx.mock
def test_error_bad_request_parsing(sync_client):
    respx.get(f"{BASE_URL}/v1/notices?unknown_param=1").mock(
        return_value=httpx.Response(
            400,
            headers={"Content-Type": "application/problem+json"},
            json={
                "type": "about:blank",
                "title": "Bad Request",
                "status": 400,
                "detail": 'unknown query parameter "unknown_param"',
            },
        )
    )

    with pytest.raises(BadRequestError) as exc_info:
        sync_client._get("/v1/notices", params={"unknown_param": "1"})

    assert exc_info.value.status == 400
    assert "unknown query parameter" in exc_info.value.detail
    assert exc_info.value.title == "Bad Request"


@respx.mock
def test_error_not_found_parsing(sync_client):
    respx.get(f"{BASE_URL}/v1/notices/nonexistent").mock(
        return_value=httpx.Response(
            404,
            headers={"Content-Type": "application/problem+json"},
            json={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "no such notice nonexistent",
            },
        )
    )

    with pytest.raises(NotFoundError) as exc_info:
        sync_client.get_notice("nonexistent")
    assert exc_info.value.status == 404
    assert exc_info.value.detail == "no such notice nonexistent"


@respx.mock
def test_error_stations_loading_parsing(sync_client):
    respx.get(f"{BASE_URL}/v1/stations/WBROK").mock(
        return_value=httpx.Response(
            503,
            headers={"Content-Type": "application/problem+json"},
            json={
                "type": "about:blank",
                "title": "Service Unavailable",
                "status": 503,
                "detail": "stations loading",
            },
        )
    )

    with pytest.raises(StationsLoadingError) as exc_info:
        sync_client.get_station("WBROK")
    assert exc_info.value.status == 503


@respx.mock
def test_iter_changes_pagination(sync_client):
    respx.get(f"{BASE_URL}/v1/changes?limit=2").mock(
        return_value=httpx.Response(
            200,
            json={
                "source": {
                    "built_at": "2026-09-23T14:53:44.417Z",
                    "fetched_at": "2026-09-23T15:28:39.935Z",
                    "checked_at": "2026-09-24T09:21:21Z",
                    "stale": False,
                },
                "events": [
                    {
                        "cursor": "1",
                        "type": "created",
                        "notice_id": "notice-1",
                        "build": "2026-09-23T14:53:44.417Z",
                        "at": "2026-09-23T15:28:39.935Z",
                    },
                    {
                        "cursor": "2",
                        "type": "extracted",
                        "notice_id": "notice-1",
                        "build": "2026-09-23T14:53:44.417Z",
                        "at": "2026-09-23T15:30:00Z",
                    },
                ],
                "next": "2",
            },
        )
    )
    respx.get(f"{BASE_URL}/v1/changes?after=2&limit=2").mock(
        return_value=httpx.Response(
            200,
            json={
                "source": {
                    "built_at": "2026-09-23T14:53:44.417Z",
                    "fetched_at": "2026-09-23T15:28:39.935Z",
                    "checked_at": "2026-09-24T09:21:21Z",
                    "stale": False,
                },
                "events": [],
                "next": "2",
            },
        )
    )

    events = list(sync_client.iter_changes(limit=2))
    assert len(events) == 2
    assert events[0].notice_id == "notice-1"
    assert events[1].type == "extracted"


@respx.mock
@pytest.mark.asyncio
async def test_async_iter_changes_pagination(async_client):
    respx.get(f"{BASE_URL}/v1/changes?limit=1").mock(
        return_value=httpx.Response(
            200,
            json={
                "source": {
                    "built_at": "2026-09-23T14:53:44.417Z",
                    "fetched_at": "2026-09-23T15:28:39.935Z",
                    "checked_at": "2026-09-24T09:21:21Z",
                    "stale": False,
                },
                "events": [
                    {
                        "cursor": "10",
                        "type": "created",
                        "notice_id": "notice-10",
                        "build": "2026-09-23T14:53:44.417Z",
                        "at": "2026-09-23T15:28:39.935Z",
                    },
                ],
                "next": "10",
            },
        )
    )
    respx.get(f"{BASE_URL}/v1/changes?after=10&limit=1").mock(
        return_value=httpx.Response(
            200,
            json={
                "source": {
                    "built_at": "2026-09-23T14:53:44.417Z",
                    "fetched_at": "2026-09-23T15:28:39.935Z",
                    "checked_at": "2026-09-24T09:21:21Z",
                    "stale": False,
                },
                "events": [],
                "next": "10",
            },
        )
    )

    events = [event async for event in async_client.iter_changes(limit=1)]
    assert len(events) == 1
    assert events[0].notice_id == "notice-10"
