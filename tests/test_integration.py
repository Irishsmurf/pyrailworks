"""Integration tests running against the live Railworks API (https://railworks.paddez.com),
or the instance RAILWORKS_BASE_URL names. Every public call must use /v2."""
import os
import warnings

import pytest
from datetime import date
from pyrailworks import (
    ApiDeprecationWarning,
    GoneError,
    RailworksClient,
    AsyncRailworksClient,
    LineName,
    NoticeStatus,
)

# RAILWORKS_BASE_URL points these tests at another instance, e.g. a railworks
# build under test in the railworks repository's CI.
BASE_URL = os.environ.get("RAILWORKS_BASE_URL", "https://railworks.paddez.com")

pytestmark = pytest.mark.integration


def _only_v2(request):
    # Every public call must use /v2: /v1's notice and health routes are retired
    # at 2026-12-01T00:00:00Z, and before then they'd still answer.
    assert request.url.path.startswith("/v2/"), request.url.path


async def _only_v2_async(request):
    _only_v2(request)


@pytest.fixture
def sync_client():
    with RailworksClient(base_url=BASE_URL) as client:
        client._client.event_hooks["request"].append(_only_v2)
        with warnings.catch_warnings():
            # /v2 routes aren't deprecated: a Deprecation header here is a failure.
            warnings.simplefilter("error", ApiDeprecationWarning)
            yield client


@pytest.fixture
async def async_client():
    async with AsyncRailworksClient(base_url=BASE_URL) as client:
        client._client.event_hooks["request"].append(_only_v2_async)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ApiDeprecationWarning)
            yield client


def test_live_health(sync_client):
    health = sync_client.get_health()
    assert health.source is not None
    assert isinstance(health.source.stale, bool)
    assert health.extraction is not None
    for ref in health.held_notices + health.low_confidence + health.needs_review:
        assert ref.title


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
    for notice in notices_resp.notices:
        assert notice.title and isinstance(notice.summary, list)
    if notices_resp.notices:
        notice = notices_resp.notices[0]
        full_notice = sync_client.get_notice(notice.id)
        assert full_notice.id == notice.id
        assert full_notice.service_group is not None
        assert full_notice.title == notice.title
        assert full_notice.day_sections is not None and full_notice.revisions
        for seg in full_notice.works_segments:
            assert isinstance(seg.from_codes, list) and isinstance(seg.to_codes, list)
        for alteration in full_notice.alterations or []:
            assert alteration.origin and alteration.destination

        # Deprecated: the revision history, without the HTML /v2 doesn't serve.
        with pytest.warns(DeprecationWarning):
            raw_resp = sync_client.get_notice_raw(notice.id)
        assert len(raw_resp.revisions) == len(full_notice.revisions)


def test_retired_v1_route_is_flagged():
    # The one deliberate /v1 call: the server's real Deprecation and Sunset
    # headers must reach the caller as an ApiDeprecationWarning, before the
    # Sunset (200) and after it (410 Gone).
    with RailworksClient(base_url=BASE_URL) as client, warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        try:
            client._get("/v1/notices", params={"line": "dart"})
        except GoneError as gone:
            assert gone.successor and gone.successor.startswith("/v2/notices")
    flagged = [w for w in record if issubclass(w.category, ApiDeprecationWarning)]
    assert flagged, [str(w.message) for w in record]
    message = flagged[0].message
    assert message.path == "/v1/notices"
    assert message.sunset is not None and message.sunset.isoformat() == "2026-12-01T00:00:00+00:00"
    assert message.successor and message.successor.startswith("/v2/notices")


def test_live_calendar_feed(sync_client):
    ics = sync_client.get_calendar_feed(station="WBROK")
    assert "BEGIN:VCALENDAR" in ics
    assert "END:VCALENDAR" in ics


@pytest.mark.asyncio
async def test_live_async_client(async_client):
    health = await async_client.get_health()
    assert health.source is not None
    assert isinstance(health.source.stale, bool)

    notices = await async_client.list_notices(status="all")
    if notices.notices:
        full_notice = await async_client.get_notice(notices.notices[0].id)
        assert full_notice.title

    stations = await async_client.list_stations()
    assert len(stations) > 0

    wbrok = await async_client.get_station("WBROK")
    assert wbrok.code == "WBROK"

    ics = await async_client.get_calendar_feed(station="WBROK")
    assert "BEGIN:VCALENDAR" in ics
