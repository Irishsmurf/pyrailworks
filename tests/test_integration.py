"""Integration tests running against the live Railworks API (https://railworks.paddez.com)."""
import pytest
from datetime import date
from pyrailworks import (
    RailworksClient,
    AsyncRailworksClient,
    LineName,
    NoticeStatus,
)

BASE_URL = "https://railworks.paddez.com"

pytestmark = pytest.mark.integration


@pytest.fixture
def sync_client():
    with RailworksClient(base_url=BASE_URL) as client:
        yield client


@pytest.fixture
async def async_client():
    async with AsyncRailworksClient(base_url=BASE_URL) as client:
        yield client


def test_live_health(sync_client):
    health = sync_client.get_health()
    assert health.source is not None
    assert isinstance(health.source.stale, bool)
    assert health.extraction is not None


def test_live_stations(sync_client):
    stations = sync_client.list_stations()
    assert len(stations) > 0
    codes = [s.code for s in stations]
    assert "WBROK" in codes

    wbrok = sync_client.get_station("WBROK")
    assert wbrok.code == "WBROK"
    assert wbrok.name == "Woodbrook"
    assert len(wbrok.lines) > 0


def test_live_station_days(sync_client):
    station_days = sync_client.get_station_days("WBROK")
    assert station_days.station.code == "WBROK"
    assert station_days.station.name == "Woodbrook"
    assert isinstance(station_days.days, list)
    if station_days.days:
        first_day = station_days.days[0]
        assert isinstance(first_day.date, date)
        assert first_day.effect is not None


def test_live_notices(sync_client):
    notices_resp = sync_client.list_notices(
        line=LineName.DART, status=[NoticeStatus.ACTIVE, NoticeStatus.EXPIRED]
    )
    assert notices_resp.source is not None
    if notices_resp.notices:
        notice = notices_resp.notices[0]
        full_notice = sync_client.get_notice(notice.id)
        assert full_notice.id == notice.id
        assert full_notice.service_group is not None

        raw_resp = sync_client.get_notice_raw(notice.id)
        assert len(raw_resp.revisions) > 0
        assert raw_resp.revisions[0].html is not None


def test_live_calendar_feed(sync_client):
    ics = sync_client.get_calendar_feed(station="WBROK")
    assert "BEGIN:VCALENDAR" in ics
    assert "END:VCALENDAR" in ics


@pytest.mark.asyncio
async def test_live_async_client(async_client):
    health = await async_client.get_health()
    assert health.source is not None
    assert isinstance(health.source.stale, bool)

    stations = await async_client.list_stations()
    assert len(stations) > 0

    wbrok = await async_client.get_station("WBROK")
    assert wbrok.code == "WBROK"

    ics = await async_client.get_calendar_feed(station="WBROK")
    assert "BEGIN:VCALENDAR" in ics
