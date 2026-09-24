"""Forward compatibility: the railworks API promises additive changes only in /v1,
and its enum lists are open, so a value this version doesn't know yet must never
stop a response from parsing. Fixtures are real API responses."""
import copy
import json
from pathlib import Path

import httpx
import pytest
import respx

import pyrailworks
from pyrailworks import ChangesResponse, NoticeResponse, RailworksClient
from pyrailworks.models import StationDaysResponse

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://railworks.paddez.com"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_fixtures_parse_as_they_are():
    NoticeResponse.model_validate(load("notice.json"))
    NoticeResponse.model_validate(load("notice_with_effects.json"))
    StationDaysResponse.model_validate(load("station_days.json"))
    ChangesResponse.model_validate(load("changes.json"))


def _mutate_notice(mutate):
    raw = copy.deepcopy(load("notice_with_effects.json"))
    raw["notice"]["alterations"] = load("notice.json")["notice"]["alterations"]
    mutate(raw["notice"])
    return NoticeResponse.model_validate(raw).notice


@pytest.mark.parametrize(
    "field, mutate, read",
    [
        ("status", lambda n: n.update(status="suspended"), lambda n: n.status),
        ("effect kind", lambda n: n["effects"][0].update(kind="platform_closed"), lambda n: n.effects[0].kind),
        ("alteration change", lambda n: n["alterations"][0].update(changes=["diverted"]), lambda n: n.alterations[0].changes[0]),
        ("extraction status", lambda n: n["extraction"].update(status="queued"), lambda n: n.extraction.status),
        ("date method", lambda n: n["date_inference"].update(method="explicit_year"), lambda n: n.date_inference.method),
        ("expansion", lambda n: n["works_segments"][0].update(expansion="partial"), lambda n: n.works_segments[0].expansion),
    ],
)
def test_unknown_enum_values_parse(field, mutate, read):
    new_value = {
        "status": "suspended", "effect kind": "platform_closed", "alteration change": "diverted",
        "extraction status": "queued", "date method": "explicit_year", "expansion": "partial",
    }[field]
    notice = _mutate_notice(mutate)
    value = read(notice)
    assert value == new_value          # still compares equal to the raw string
    assert value.value == new_value    # the value is preserved
    assert not value.is_known          # and callers can tell it's new


def test_known_values_are_known():
    notice = _mutate_notice(lambda n: None)
    assert notice.status.is_known and notice.effects[0].kind.is_known


def test_unknown_station_day_effect_and_event_type():
    days = load("station_days.json")
    days["days"][0]["effect"] = "platform_closed"
    assert StationDaysResponse.model_validate(days).days[0].effect == "platform_closed"
    changes = load("changes.json")
    changes["events"][0]["type"] = "rescheduled"
    assert ChangesResponse.model_validate(changes).events[0].type == "rescheduled"


@respx.mock
def test_iter_changes_survives_a_new_event_type():
    page = load("changes.json")
    page["events"][0]["type"] = "rescheduled"
    last = page["next"]
    respx.get(f"{BASE_URL}/v1/changes").mock(
        side_effect=lambda request: httpx.Response(
            200, json=page if "after" not in request.url.params else {**page, "events": [], "next": last}
        )
    )
    with RailworksClient(base_url=BASE_URL) as client:
        types = [e.type for e in client.iter_changes(since="2026-01-01T00:00:00Z")]
    assert "rescheduled" in types


def test_new_fields_are_ignored():
    raw = load("notice_with_effects.json")
    raw["notice"]["a_field_from_the_future"] = {"anything": 1}
    raw["brand_new_top_level"] = True
    NoticeResponse.model_validate(raw)


@respx.mock
def test_user_agent_names_this_version():
    route = respx.get(f"{BASE_URL}/v1/health").mock(return_value=httpx.Response(200, json={}))
    with RailworksClient(base_url=BASE_URL) as client:
        try:
            client.get_health()
        except Exception:
            pass
    assert route.calls[0].request.headers["User-Agent"] == f"pyrailworks/{pyrailworks.__version__}"
