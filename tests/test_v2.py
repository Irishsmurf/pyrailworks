"""/v2 models, the deprecated aliases of fields /v2 dropped, and the warnings.

Fixtures are real /v2 responses (from railworks' fixture server)."""
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from pyrailworks import (
    API_VERSION,
    ApiDeprecationWarning,
    AsyncRailworksClient,
    GoneError,
    Health,
    NoticeResponse,
    RailworksClient,
)

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://railworks.paddez.com"

V1_HEADERS = {
    "Deprecation": "@1794096000",
    "Sunset": "Tue, 01 Dec 2026 00:00:00 GMT",
    "Link": '</v1/openapi.yaml>; rel="service-desc", </docs>; rel="service-doc", '
    '</v2/notices?line=dart>; rel="successor-version", '
    '</docs#migrating-to-v2>; rel="deprecation"; type="text/html"',
}


def load(name):
    return json.loads((FIXTURES / name).read_text())


def notice(name="notice_with_effects.json"):
    return NoticeResponse.model_validate(load(name)).notice


# --- models -----------------------------------------------------------------


def test_v2_is_the_default():
    assert API_VERSION == "v2"


def test_notice_has_title_and_summary():
    n = notice()
    assert n.title.startswith("DART: ")
    assert isinstance(n.summary, list) and n.summary
    assert all(isinstance(line, str) for line in n.summary)


def test_places_are_named_from_the_station_list():
    n = notice()
    seg = n.works_segments[0]
    assert (seg.from_, seg.to) == ("Dun Laoghaire", "Wicklow")
    assert seg.from_codes and seg.to_codes and seg.stations
    effect = n.effects[0]
    assert effect.from_ == "Dun Laoghaire" and effect.station_codes
    # an Effect without a stretch has no from/to
    assert n.effects[1].from_ is None and n.effects[1].to is None


def test_unknown_places_are_absent():
    raw = load("notice_with_effects.json")
    seg = raw["notice"]["works_segments"][0]
    del seg["from"], seg["to"]
    seg["expansion"] = "unresolved"
    parsed = NoticeResponse.model_validate(raw).notice.works_segments[0]
    assert parsed.from_ is None and parsed.to is None


def test_service_alterations_are_named_from_codes():
    alteration = notice("notice.json").alterations[0]
    assert alteration.origin and alteration.destination
    assert alteration.origin_codes and alteration.destination_codes
    assert isinstance(alteration.station_codes, list)


def test_day_sections_have_days_only():
    raw = load("notice.json")
    raw["notice"]["day_sections"] = [{"days": ["2026-09-26", "2026-09-27"]}]
    section = NoticeResponse.model_validate(raw).notice.day_sections[0]
    assert [d.isoformat() for d in section.days] == ["2026-09-26", "2026-09-27"]


def test_revisions_have_extended_and_no_html():
    rev = notice().revisions[0]
    assert rev.extended is False and rev.summary == "first published"


@pytest.mark.parametrize(
    "get, field",
    [
        (lambda n: n.works_segments[0], "quote"),
        (lambda n: n.works_segments[0], "clause"),
        (lambda n: n.effects[0], "quote"),
        (lambda n: n.alterations[0], "quote"),
        (lambda n: n.alterations[0], "stations"),
    ],
)
def test_upstream_text_fields_are_gone(get, field):
    raw = load("notice_with_effects.json")
    raw["notice"]["alterations"] = load("notice.json")["notice"]["alterations"]
    model = get(NoticeResponse.model_validate(raw).notice)
    assert not hasattr(model, field)


def test_withdrawn_reason_is_an_open_enum():
    raw = load("notice.json")
    raw["notice"].update(status="withdrawn", withdrawn_reason="left_page")
    assert NoticeResponse.model_validate(raw).notice.withdrawn_reason == "left_page"
    raw["notice"]["withdrawn_reason"] = "operator_cancelled"
    reason = NoticeResponse.model_validate(raw).notice.withdrawn_reason
    assert reason == "operator_cancelled" and not reason.is_known


def test_health_names_notices_by_title():
    health = Health.model_validate(load("health.json"))
    assert health.needs_review and health.needs_review[0].title
    assert health.needs_review[0].reasons[0] == "no_works_segment"
    assert health.no_stations == 1 and health.empty_detail == 0


def test_health_refs_and_reasons():
    raw = load("health.json")
    raw["held_notices"] = [{"id": "a", "service_group": "DART Services", "title": "DART: x", "reason": "group_vanished"}]
    raw["low_confidence"] = [{"id": "b", "service_group": "DART Services", "title": "DART: y", "confidence": 0.3}]
    raw["needs_review"][0]["reasons"] = ["no_works_segment", "a_new_reason"]
    health = Health.model_validate(raw)
    assert health.held_notices[0].reason == "group_vanished"
    assert health.low_confidence[0].title == "DART: y"
    assert not health.needs_review[0].reasons[1].is_known


# --- deprecated aliases -----------------------------------------------------


def _one_deprecation(record):
    deprecations = [w for w in record if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1, [str(w.message) for w in record]
    # Points at the caller's line, not at pyrailworks.
    assert deprecations[0].filename == __file__
    return deprecations[0]


def test_heading_is_a_deprecated_alias_of_title():
    n = notice()
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        assert n.heading == n.title
    assert "title" in str(_one_deprecation(record).message)


def test_detail_is_a_deprecated_join_of_summary():
    n = notice()
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        assert n.detail == "\n".join(n.summary)
    assert "summary" in str(_one_deprecation(record).message)


def test_revision_html_is_deprecated_and_none():
    rev = notice().revisions[0]
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        assert rev.html is None
    _one_deprecation(record)


def test_health_ref_heading_is_a_deprecated_alias_of_title():
    ref = Health.model_validate(load("health.json")).needs_review[0]
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        assert ref.heading == ref.title
    _one_deprecation(record)


def test_current_fields_dont_warn():
    n = notice()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _ = (n.title, n.summary, n.works_segments, n.revisions[0].summary)


@respx.mock
def test_get_notice_raw_is_a_deprecated_view_of_v2_revisions():
    route = respx.get(f"{BASE_URL}/v2/notices/7d33651427c9").mock(
        return_value=httpx.Response(200, json=load("notice_with_effects.json"))
    )
    with RailworksClient(base_url=BASE_URL) as client, warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        raw = client.get_notice_raw("7d33651427c9")
    assert "get_notice" in str(_one_deprecation(record).message)
    assert route.called
    assert len(raw.revisions) == 1 and raw.revisions[0].summary == "first published"


@respx.mock
async def test_async_get_notice_raw_is_a_deprecated_view_of_v2_revisions():
    respx.get(f"{BASE_URL}/v2/notices/7d33651427c9").mock(
        return_value=httpx.Response(200, json=load("notice_with_effects.json"))
    )
    async with AsyncRailworksClient(base_url=BASE_URL) as client:
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            raw = await client.get_notice_raw("7d33651427c9")
    _one_deprecation(record)
    assert raw.revisions[0].build is not None


# --- every call uses /v2 ----------------------------------------------------


def _every_method(client):
    return [
        lambda: client.get_health(),
        lambda: client.list_notices(),
        lambda: client.get_notice("7d33651427c9"),
        lambda: client.list_changes(),
        lambda: client.list_stations(),
        lambda: client.get_station("WBROK"),
        lambda: client.get_station_days("WBROK"),
        lambda: client.get_calendar_feed(),
    ]


@respx.mock
def test_every_call_uses_v2():
    paths = []
    respx.route(host="railworks.paddez.com").mock(
        side_effect=lambda request: paths.append(request.url.path) or httpx.Response(500)
    )
    with RailworksClient(base_url=BASE_URL) as client:
        for call in _every_method(client):
            with pytest.raises(httpx.HTTPStatusError):
                call()
    assert len(paths) == 8 and all(p.startswith("/v2/") for p in paths), paths


# --- the server's Deprecation and Sunset headers ----------------------------


def _deprecated_route(**headers):
    return respx.get(f"{BASE_URL}/v2/health").mock(
        return_value=httpx.Response(200, headers=headers or V1_HEADERS, json=load("health.json"))
    )


@respx.mock
def test_deprecation_headers_warn():
    _deprecated_route()
    with RailworksClient(base_url=BASE_URL) as client, pytest.warns(ApiDeprecationWarning) as record:
        client.get_health()
    w = record[0]
    assert issubclass(w.category, FutureWarning)  # shown by default, unlike DeprecationWarning
    assert w.filename == __file__
    msg = w.message
    assert msg.path == "/v2/health"
    assert msg.sunset == datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert msg.deprecated_at == datetime(2026, 11, 8, tzinfo=timezone.utc)
    assert msg.successor == "/v2/notices?line=dart"
    assert "2026-12-01T00:00:00+00:00" in str(msg) and "/v2/notices instead" in str(msg)


@respx.mock
async def test_async_deprecation_headers_warn():
    _deprecated_route()
    async with AsyncRailworksClient(base_url=BASE_URL) as client:
        with pytest.warns(ApiDeprecationWarning) as record:  # noqa: SIM117 - async with and with
            await client.get_health()
    assert record[0].filename == __file__


@respx.mock
def test_sunset_alone_warns():
    _deprecated_route(Sunset="Tue, 01 Dec 2026 00:00:00 GMT")
    with RailworksClient(base_url=BASE_URL) as client, pytest.warns(ApiDeprecationWarning) as record:
        client.get_health()
    assert record[0].message.deprecated_at is None and record[0].message.successor is None


@respx.mock
def test_malformed_deprecation_headers_still_warn_and_never_raise():
    _deprecated_route(Deprecation="?1", Sunset="soon", Link="<<<not a link")
    with RailworksClient(base_url=BASE_URL) as client, pytest.warns(ApiDeprecationWarning) as record:
        health = client.get_health()
    assert health.source is not None
    assert record[0].message.sunset is None and record[0].message.deprecated_at is None


@respx.mock
def test_no_deprecation_headers_no_warning():
    respx.get(f"{BASE_URL}/v2/health").mock(return_value=httpx.Response(200, json=load("health.json")))
    with RailworksClient(base_url=BASE_URL) as client, warnings.catch_warnings():
        warnings.simplefilter("error")
        client.get_health()


@respx.mock
def test_gone_after_the_sunset():
    respx.get(f"{BASE_URL}/v2/health").mock(
        return_value=httpx.Response(
            410,
            headers={"Content-Type": "application/problem+json", **V1_HEADERS},
            json={
                "type": "about:blank",
                "title": "Gone",
                "status": 410,
                "detail": "/v1/health was retired on 1 December 2026",
                "successor": "/v2/health",
            },
        )
    )
    with (
        RailworksClient(base_url=BASE_URL) as client,
        pytest.warns(ApiDeprecationWarning),
        pytest.raises(GoneError) as exc_info,
    ):
        client.get_health()
    assert exc_info.value.status == 410 and exc_info.value.successor == "/v2/health"
