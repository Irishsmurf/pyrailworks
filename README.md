# pyrailworks

Python client library for the Public RO Railworks API ([https://railworks.paddez.com/docs](https://railworks.paddez.com/docs)).

Provides queryable access to Iarnród Éireann's (Irish Rail) planned engineering works, station days, change logs, and iCalendar feeds.

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
        print(f"Notice {notice.id}: {notice.heading} ({notice.starts_on} to {notice.ends_on})")

    # 5. Follow changes with automatic cursor traversal
    for event in client.iter_changes():
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

        async for event in client.iter_changes():
            print("Notice changed:", event.notice_id)

asyncio.run(main())
```

## Features

- **Both Sync & Async**: `RailworksClient` and `AsyncRailworksClient` powered by `httpx`.
- **Strict Data Validation**: Pydantic v2 data models for type safety, validation, and auto-completion.
- **Problem Details Handling**: Full support for RFC 9457 errors with specific exceptions (`BadRequestError`, `NotFoundError`, `StationsLoadingError`).
- **Change Log Streaming**: Helper generators (`iter_changes()`) handling opaque cursor pagination.
- **Calendar Feeds**: Raw iCalendar text download via `get_calendar_feed()`.
