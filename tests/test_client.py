"""Tests for client, parsing, exceptions, and live API."""
import pytest
import respx
import httpx
from datetime import date
from pyrailworks import (
    RailworksClient,
    AsyncRailworksClient,
    BadRequestError,
    NotFoundError,
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
def test_error_problem_document_parsing():
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

    with RailworksClient(base_url=BASE_URL) as client:
        with pytest.raises(BadRequestError) as exc_info:
            client._get("/v1/notices", params={"unknown_param": "1"})

        assert exc_info.value.status == 400
        assert "unknown query parameter" in exc_info.value.detail


@respx.mock
def test_not_found_error_parsing():
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

    with RailworksClient(base_url=BASE_URL) as client:
        with pytest.raises(NotFoundError) as exc_info:
            client.get_notice("nonexistent")
        assert exc_info.value.status == 404


@respx.mock
def test_iter_changes_pagination():
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

    with RailworksClient(base_url=BASE_URL) as client:
        events = list(client.iter_changes(limit=2))
        assert len(events) == 2
        assert events[0].notice_id == "notice-1"
        assert events[1].type == "extracted"


def test_live_health(sync_client):
    health = sync_client.get_health()
    assert health.source is not None
    assert isinstance(health.source.stale, bool)


def test_live_stations(sync_client):
    stations = sync_client.list_stations()
    assert len(stations) > 0
    wbrok = sync_client.get_station("WBROK")
    assert wbrok.code == "WBROK"
    assert wbrok.name == "Woodbrook"


def test_live_station_days(sync_client):
    station_days = sync_client.get_station_days("WBROK")
    assert station_days.station.code == "WBROK"
    assert isinstance(station_days.days, list)


def test_live_notices(sync_client):
    notices_resp = sync_client.list_notices(line=LineName.DART, status=[NoticeStatus.ACTIVE, NoticeStatus.EXPIRED])
    assert notices_resp.source is not None
    if notices_resp.notices:
        notice = notices_resp.notices[0]
        full_notice = sync_client.get_notice(notice.id)
        assert full_notice.id == notice.id
        raw_resp = sync_client.get_notice_raw(notice.id)
        assert len(raw_resp.revisions) > 0


def test_live_calendar_feed(sync_client):
    ics = sync_client.get_calendar_feed(station="WBROK")
    assert "BEGIN:VCALENDAR" in ics


@pytest.mark.asyncio
async def test_live_async_client(async_client):
    health = await async_client.get_health()
    assert health.source is not None

    stations = await async_client.list_stations()
    assert len(stations) > 0
