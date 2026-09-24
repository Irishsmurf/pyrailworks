"""HTTP Client implementation for pyrailworks."""
from __future__ import annotations

from datetime import date, datetime
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
    Union,
)
import httpx

from pyrailworks._version import __version__

from pyrailworks.exceptions import (
    BadRequestError,
    NotFoundError,
    ProblemError,
    RailworksError,
    StationsLoadingError,
)
from pyrailworks.models import (
    ChangeEvent,
    ChangesResponse,
    Health,
    LineName,
    NoticeResponse,
    NoticeStatus,
    NoticesResponse,
    RawNoticeResponse,
    StationDay,
    StationDaysResponse,
    StationResponse,
    StationsResponse,
    WorksNotice,
    Station,
)

DEFAULT_BASE_URL = "https://railworks.paddez.com"


def _format_date(val: Union[date, str, None]) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    return str(val)


def _format_datetime(val: Union[datetime, str, None]) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _format_status(
    status: Union[NoticeStatus, str, List[Union[NoticeStatus, str]], None]
) -> Optional[str]:
    if status is None:
        return None
    if isinstance(status, (list, tuple, set)):
        return ",".join(
            s.value if isinstance(s, NoticeStatus) else str(s) for s in status
        )
    if isinstance(status, NoticeStatus):
        return status.value
    return str(status)


def _handle_error_response(response: httpx.Response) -> None:
    if response.is_success or response.status_code == 304:
        return

    content_type = response.headers.get("content-type", "")
    if "application/problem+json" in content_type:
        try:
            data = response.json()
            title = data.get("title", "Error")
            detail = data.get("detail", response.text)
            type_ = data.get("type")
            status = data.get("status", response.status_code)

            if status == 400:
                raise BadRequestError(status=status, title=title, detail=detail, type_=type_)
            if status == 404:
                raise NotFoundError(status=status, title=title, detail=detail, type_=type_)
            if status == 503:
                raise StationsLoadingError(status=status, title=title, detail=detail, type_=type_)

            raise ProblemError(status=status, title=title, detail=detail, type_=type_)
        except (ValueError, KeyError):
            pass

    response.raise_for_status()


class RailworksClient:
    """Synchronous client for the Railworks API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        default_headers = {
            "User-Agent": f"pyrailworks/{__version__}",
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
                headers=default_headers,
                follow_redirects=True,
            )
            self._owns_client = True

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> RailworksClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        filtered_params = {k: v for k, v in (params or {}).items() if v is not None}
        resp = self._client.get(path, params=filtered_params, headers=headers)
        _handle_error_response(resp)
        return resp

    def get_health(self) -> Health:
        """Get health status, freshness and backend diagnostics."""
        resp = self._get("/v1/health")
        return Health.model_validate(resp.json())

    def list_notices(
        self,
        *,
        from_date: Union[date, str, None] = None,
        to_date: Union[date, str, None] = None,
        status: Union[NoticeStatus, str, List[Union[NoticeStatus, str]], None] = None,
        station: Optional[str] = None,
        line: Union[LineName, str, None] = None,
        group: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> NoticesResponse:
        """List Works Notices with any day in the given window."""
        params: Dict[str, Any] = {
            "from": _format_date(from_date),
            "to": _format_date(to_date),
            "status": _format_status(status),
            "station": station,
            "line": line.value if isinstance(line, LineName) else line,
            "group": group,
            "min_confidence": min_confidence,
        }
        resp = self._get("/v1/notices", params=params)
        return NoticesResponse.model_validate(resp.json())

    def get_notice(self, notice_id: str) -> WorksNotice:
        """Get a full Works Notice by id with revisions, day sections and alterations."""
        resp = self._get(f"/v1/notices/{notice_id}")
        data = resp.json()
        return WorksNotice.model_validate(data["notice"])

    def get_notice_raw(self, notice_id: str) -> RawNoticeResponse:
        """Get verbatim upstream HTML for all revisions of a notice."""
        resp = self._get(f"/v1/notices/{notice_id}/raw")
        return RawNoticeResponse.model_validate(resp.json())

    def list_changes(
        self,
        *,
        after: Optional[str] = None,
        since: Union[datetime, str, None] = None,
        limit: Optional[int] = None,
    ) -> ChangesResponse:
        """Fetch a page of change events from the append-only change log."""
        params: Dict[str, Any] = {
            "after": after,
            "since": _format_datetime(since),
            "limit": limit,
        }
        resp = self._get("/v1/changes", params=params)
        return ChangesResponse.model_validate(resp.json())

    def iter_changes(
        self,
        *,
        since: Union[datetime, str, None] = None,
        after: Optional[str] = None,
        limit: int = 500,
    ) -> Iterator[ChangeEvent]:
        """Convenience generator that yields change events and automatically traverses pages."""
        cursor = after
        initial_since = since if cursor is None else None

        while True:
            resp = self.list_changes(after=cursor, since=initial_since, limit=limit)
            initial_since = None
            if not resp.events:
                break
            for event in resp.events:
                yield event
            if resp.next == cursor:
                break
            cursor = resp.next

    def list_stations(self) -> List[Station]:
        """List all Irish Rail stations served by timetabled trains."""
        resp = self._get("/v1/stations")
        data = resp.json()
        return StationsResponse.model_validate(data).stations

    def get_station(self, code: str) -> Station:
        """Get details for a single station by code."""
        resp = self._get(f"/v1/stations/{code}")
        data = resp.json()
        return StationResponse.model_validate(data).station

    def get_station_days(
        self,
        code: str,
        *,
        from_date: Union[date, str, None] = None,
        to_date: Union[date, str, None] = None,
    ) -> StationDaysResponse:
        """Check whether a station is affected, and on which dates."""
        params: Dict[str, Any] = {
            "from": _format_date(from_date),
            "to": _format_date(to_date),
        }
        resp = self._get(f"/v1/stations/{code}/days", params=params)
        return StationDaysResponse.model_validate(resp.json())

    def get_calendar_feed(
        self,
        *,
        from_date: Union[date, str, None] = None,
        station: Optional[str] = None,
        line: Union[LineName, str, None] = None,
        group: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> str:
        """Download the raw iCalendar (ICS) text."""
        params: Dict[str, Any] = {
            "from": _format_date(from_date),
            "station": station,
            "line": line.value if isinstance(line, LineName) else line,
            "group": group,
            "min_confidence": min_confidence,
        }
        resp = self._get(
            "/v1/feeds/notices.ics",
            params=params,
            headers={"Accept": "text/calendar, text/plain"},
        )
        return resp.text


class AsyncRailworksClient:
    """Asynchronous client for the Railworks API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        default_headers = {
            "User-Agent": f"pyrailworks/{__version__}",
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout,
                headers=default_headers,
                follow_redirects=True,
            )
            self._owns_client = True

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncRailworksClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        filtered_params = {k: v for k, v in (params or {}).items() if v is not None}
        resp = await self._client.get(path, params=filtered_params, headers=headers)
        _handle_error_response(resp)
        return resp

    async def get_health(self) -> Health:
        """Get health status, freshness and backend diagnostics."""
        resp = await self._get("/v1/health")
        return Health.model_validate(resp.json())

    async def list_notices(
        self,
        *,
        from_date: Union[date, str, None] = None,
        to_date: Union[date, str, None] = None,
        status: Union[NoticeStatus, str, List[Union[NoticeStatus, str]], None] = None,
        station: Optional[str] = None,
        line: Union[LineName, str, None] = None,
        group: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> NoticesResponse:
        """List Works Notices with any day in the given window."""
        params: Dict[str, Any] = {
            "from": _format_date(from_date),
            "to": _format_date(to_date),
            "status": _format_status(status),
            "station": station,
            "line": line.value if isinstance(line, LineName) else line,
            "group": group,
            "min_confidence": min_confidence,
        }
        resp = await self._get("/v1/notices", params=params)
        return NoticesResponse.model_validate(resp.json())

    async def get_notice(self, notice_id: str) -> WorksNotice:
        """Get a full Works Notice by id with revisions, day sections and alterations."""
        resp = await self._get(f"/v1/notices/{notice_id}")
        data = resp.json()
        return WorksNotice.model_validate(data["notice"])

    async def get_notice_raw(self, notice_id: str) -> RawNoticeResponse:
        """Get verbatim upstream HTML for all revisions of a notice."""
        resp = await self._get(f"/v1/notices/{notice_id}/raw")
        return RawNoticeResponse.model_validate(resp.json())

    async def list_changes(
        self,
        *,
        after: Optional[str] = None,
        since: Union[datetime, str, None] = None,
        limit: Optional[int] = None,
    ) -> ChangesResponse:
        """Fetch a page of change events from the append-only change log."""
        params: Dict[str, Any] = {
            "after": after,
            "since": _format_datetime(since),
            "limit": limit,
        }
        resp = await self._get("/v1/changes", params=params)
        return ChangesResponse.model_validate(resp.json())

    async def iter_changes(
        self,
        *,
        since: Union[datetime, str, None] = None,
        after: Optional[str] = None,
        limit: int = 500,
    ) -> AsyncIterator[ChangeEvent]:
        """Convenience async generator that yields change events and automatically traverses pages."""
        cursor = after
        initial_since = since if cursor is None else None

        while True:
            resp = await self.list_changes(after=cursor, since=initial_since, limit=limit)
            initial_since = None
            if not resp.events:
                break
            for event in resp.events:
                yield event
            if resp.next == cursor:
                break
            cursor = resp.next

    async def list_stations(self) -> List[Station]:
        """List all Irish Rail stations served by timetabled trains."""
        resp = await self._get("/v1/stations")
        data = resp.json()
        return StationsResponse.model_validate(data).stations

    async def get_station(self, code: str) -> Station:
        """Get details for a single station by code."""
        resp = await self._get(f"/v1/stations/{code}")
        data = resp.json()
        return StationResponse.model_validate(data).station

    async def get_station_days(
        self,
        code: str,
        *,
        from_date: Union[date, str, None] = None,
        to_date: Union[date, str, None] = None,
    ) -> StationDaysResponse:
        """Check whether a station is affected, and on which dates."""
        params: Dict[str, Any] = {
            "from": _format_date(from_date),
            "to": _format_date(to_date),
        }
        resp = await self._get(f"/v1/stations/{code}/days", params=params)
        return StationDaysResponse.model_validate(resp.json())

    async def get_calendar_feed(
        self,
        *,
        from_date: Union[date, str, None] = None,
        station: Optional[str] = None,
        line: Union[LineName, str, None] = None,
        group: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> str:
        """Download the raw iCalendar (ICS) text."""
        params: Dict[str, Any] = {
            "from": _format_date(from_date),
            "station": station,
            "line": line.value if isinstance(line, LineName) else line,
            "group": group,
            "min_confidence": min_confidence,
        }
        resp = await self._get(
            "/v1/feeds/notices.ics",
            params=params,
            headers={"Accept": "text/calendar, text/plain"},
        )
        return resp.text
