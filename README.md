# pyrailworks

Python client library for the Public RO Railworks API ([https://railworks.paddez.com/docs](https://railworks.paddez.com/docs)).

Provides queryable access to Iarnród Éireann's (Irish Rail) planned engineering works, station days, change logs, and iCalendar feeds.

pyrailworks 0.3 uses the railworks **`/v2`** API. **Upgrading from 0.2 or earlier? Upgrade before 1 December 2026**, when `/v1`'s notice and health routes are retired: see [Migrating from 0.2](#migrating-from-02-v1).

## Installation

```bash
pip install pyrailworks
```

## Quick Start

### Synchronous Client

```python
from pyrailworks import RailworksClient, LineName

with RailworksClient() as client:
    # 1. Health check
    health = client.get_health()
    print("Upstream checked at:", health.source.checked_at)

    # 2. List stations
    stations = client.list_stations()
    print(f"Total stations: {len(stations)}")

    # 3. Check affected days for a station
    days_resp = client.get_station_days("WBROK")
    for day in days_resp.days:
        print(f"Station {days_resp.station.name} affected on {day.date}: {day.effect.value}")

    # 4. List active notices on a line
    notices = client.list_notices(line=LineName.DART, status="active")
    for notice in notices.notices:
        print(f"Notice {notice.id}: {notice.title} ({notice.starts_on} to {notice.ends_on})")
        for line in notice.summary:
            print("   ", line)

    # 5. One notice in full: Works Segments, Effects and Service Alterations
    notice = client.get_notice(notices.notices[0].id)
    for segment in notice.works_segments:
        print("Works between", segment.from_, "and", segment.to, segment.stations)
    for alteration in notice.alterations or []:
        print(alteration.departs, alteration.origin, "→", alteration.destination,
              [change.value for change in alteration.changes])

    # 6. Follow changes with automatic cursor traversal (start with since=, or after= a saved cursor)
    for event in client.iter_changes(since="2026-09-01T00:00:00Z"):
        print(f"Change event: {event.type.value} on notice {event.notice_id}")
```

### Asynchronous Client

```python
import asyncio
from pyrailworks import AsyncRailworksClient

async def main():
    async with AsyncRailworksClient() as client:
        health = await client.get_health()
        print("Backend stale:", health.source.stale)

        async for event in client.iter_changes(since="2026-09-01T00:00:00Z"):
            print("Notice changed:", event.notice_id)

asyncio.run(main())
```

## Notices: facts, not upstream text

railworks publishes facts and its own wording, not Iarnród Éireann's text. A `WorksNotice` has:

- **`title`**: a one-line name generated from the facts, e.g. `"DART: no trains Grand Canal Dock–Bray · Sat 24–Mon 26 Oct"`.
- **`summary`**: the facts behind it, one line each (days, Works Segments, Effects, Service Alterations).
- **`days`, `starts_on`, `ends_on`, `until`**: the dates. `title` and `summary` may be reworded as railworks improves them, so display them but don't parse them.
- **`works_segments`**, **`effects`** and (single notices) **`alterations`**: places are named from railworks' station list. A Works Segment's or Effect's `from_`/`to` is `None` when the place isn't known; the station codes are always there.

## Compatibility

The Railworks API only makes additive changes within a version (`/v2` now): new fields, endpoints and query parameters, and **new enum values**. pyrailworks is built to keep working through all of them:

- **Unknown fields** are ignored.
- **Unknown enum values** (a new effect kind, change-event type or status) parse as an `UNKNOWN` member that keeps the raw value, still compares equal to the string, and has `is_known == False`:

  ```python
  for event in client.iter_changes(since="2026-09-01T00:00:00Z"):
      if not event.type.is_known:
          log.info("new event type %s: consider upgrading pyrailworks", event.type.value)
  ```

- Requests identify the client version (`User-Agent: pyrailworks/<version>`), so the API can see which versions are in use before retiring anything.

A breaking change ships as a new version (as `/v2` did), served alongside the old one, with `Deprecation` and `Sunset` headers on what's being retired. pyrailworks turns those headers into an **`ApiDeprecationWarning`**, a `FutureWarning` that Python shows by default, naming the route, its `sunset` and its `successor`. Once a retired route is gone, it raises **`GoneError`** (410). Either one means it's time to upgrade pyrailworks:

```python
import warnings
from pyrailworks import ApiDeprecationWarning

warnings.simplefilter("error", ApiDeprecationWarning)  # e.g. fail your CI instead of only warning
```

The railworks repository runs this package's integration tests against every change to the API, and a nightly job here runs them against the live API and opens an issue if they fail.

## Migrating from 0.2 (`/v1`)

From **1 December 2026, 00:00 in Dublin (`2026-12-01T00:00:00Z`)**, railworks answers `410 Gone` on `/v1/notices`, `/v1/notices/{id}`, `/v1/notices/{id}/raw` and `/v1/health`. In pyrailworks 0.2.x, `list_notices()`, `get_notice()`, `get_notice_raw()` and `get_health()` stop working then. Upgrade to 0.3:

```bash
pip install --upgrade "pyrailworks>=0.3"
```

Ids, cursors, query parameters and errors are unchanged, and most code needs nothing else. Fields that `/v2` renamed still work in 0.3, with a `DeprecationWarning`. Fields with no successor are removed, so a type checker finds them:

| 0.2 | 0.3 |
|---|---|
| `notice.heading` | `notice.title` (`heading` is a deprecated alias) |
| `notice.detail` | `notice.summary`, a list of lines (`detail` is a deprecated alias that joins them) |
| `client.get_notice_raw(id)` | `client.get_notice(id).revisions` (`get_notice_raw` is deprecated, and its revisions' `html` is always `None`) |
| `health.held_notices[i].heading`, `health.low_confidence[i].heading` | `.title` (`heading` is a deprecated alias) |
| `day_section.heading` | removed: Day Sections have `days` only |
| `quote` on Works Segments, Effects and Service Alterations, `WorksSegment.clause` | removed |
| `ServiceAlteration.stations` (as written) | `ServiceAlteration.station_codes` |

The full list is in the [CHANGELOG](CHANGELOG.md). To find the deprecated uses, run your tests with `-W error::DeprecationWarning`, or mypy with `--enable-error-code deprecated`. There's no option to call `/v1` from 0.3: if you need `/v1`'s verbatim text until the Sunset, stay on `pyrailworks<0.3`.

## Features

- **Both Sync & Async**: `RailworksClient` and `AsyncRailworksClient` powered by `httpx`.
- **Strict Data Validation**: Pydantic v2 data models for type safety, validation, and auto-completion.
- **Problem Details Handling**: Full support for RFC 9457 errors with specific exceptions (`BadRequestError`, `NotFoundError`, `GoneError`, `StationsLoadingError`).
- **Deprecation Warnings**: `Deprecation` and `Sunset` response headers become an `ApiDeprecationWarning`.
- **Change Log Streaming**: Helper generators (`iter_changes()`) handling opaque cursor pagination.
- **Calendar Feeds**: Raw iCalendar text download via `get_calendar_feed()`.
