"""Pydantic data models for the Railworks API."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from typing_extensions import deprecated

# Fields /v2 dropped are kept as deprecated aliases of their successors where
# there is one (see the CHANGELOG): each warns with DeprecationWarning at the
# caller's line. Messages are literals so type checkers can report them.


class OpenEnum(str, Enum):
    """An enum that accepts values it doesn't know yet.

    The Railworks API only makes additive changes within a version, and its
    enum lists are open: a new effect kind or change-event type may appear without
    a new API version. An unknown value parses as a pseudo-member named
    ``UNKNOWN`` that keeps the raw value, still compares equal to the string,
    and reports ``is_known`` as False, so a new value never breaks a response.
    """

    @classmethod
    def _missing_(cls, value: object) -> "OpenEnum | None":
        if not isinstance(value, str):
            return None
        member = str.__new__(cls, value)
        member._name_ = "UNKNOWN"
        member._value_ = value
        return member

    @property
    def is_known(self) -> bool:
        """False for a value this version of pyrailworks doesn't know yet."""
        return self._name_ != "UNKNOWN"


class LineName(OpenEnum):
    DART = "dart"
    NORTHERN_COMMUTERS = "northern-commuters"
    BELFAST = "belfast"
    ROSSLARE = "rosslare"
    MAYNOOTH_LONGFORD_SLIGO = "maynooth-longford-sligo"
    PORTLAOISE_COMMUTERS = "portlaoise-commuters"
    CORK_LIMERICK_TRALEE = "cork-limerick-tralee"
    COBH_MIDLETON = "cobh-midleton"
    GALWAY_WESTPORT = "galway-westport"
    WATERFORD = "waterford"
    WESTERN_RAIL_CORRIDOR = "western-rail-corridor"
    WATERFORD_TO_LIMERICK = "waterford-to-limerick"
    BALLYBROPHY = "ballybrophy"


class NoticeStatus(OpenEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class EffectKind(OpenEnum):
    NO_SERVICE = "no_service"
    STATION_CLOSED = "station_closed"
    BUS_REPLACEMENT = "bus_replacement"
    REDUCED_SERVICE = "reduced_service"
    OTHER = "other"


class AlterationChange(OpenEnum):
    CANCELLED = "cancelled"
    BUS_REPLACED = "bus_replaced"
    TERMINATES_SHORT = "terminates_short"
    STARTS_SHORT = "starts_short"
    RETIMED = "retimed"
    SKIPS_STOPS = "skips_stops"
    OTHER = "other"


class ExtractionStatus(OpenEnum):
    DISABLED = "disabled"
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class DateInferenceMethod(OpenEnum):
    WEEKDAY = "weekday"
    NEXT_OCCURRENCE = "next_occurrence"


class SegmentExpansion(OpenEnum):
    OK = "ok"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class WithdrawnReason(OpenEnum):
    LEFT_PAGE = "left_page"
    GROUP_VANISHED = "group_vanished"
    MASS_WITHDRAWAL_CONFIRMED = "mass_withdrawal_confirmed"


class HeldReason(OpenEnum):
    GROUP_VANISHED = "group_vanished"
    MASS_WITHDRAWAL = "mass_withdrawal"


class ReviewReason(OpenEnum):
    NO_WORKS_SEGMENT = "no_works_segment"
    EMPTY_DETAIL = "empty_detail"


class ChangeEventType(OpenEnum):
    CREATED = "created"
    REVISED = "revised"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"
    EXTRACTED = "extracted"


class Source(BaseModel):
    built_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    checked_at: Optional[datetime] = None
    stale: bool


class DateCorrection(BaseModel):
    from_: date = Field(..., alias="from")
    to: date


class DateInference(BaseModel):
    method: DateInferenceMethod
    corrections: List[DateCorrection] = Field(default_factory=list)
    conflicts: List[date] = Field(default_factory=list)
    prose_missing: List[date] = Field(default_factory=list)
    prose_extra: List[date] = Field(default_factory=list)


class DaySection(BaseModel):
    """A Day Section, by its days (/v2 dropped its published heading)."""

    days: List[date] = Field(default_factory=list)


class WorksSegment(BaseModel):
    """A track section where works take place.

    ``from_`` and ``to`` are names from railworks' station list, None when the
    place isn't known; the codes are always there.
    """

    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    from_codes: List[str] = Field(default_factory=list)
    to_codes: List[str] = Field(default_factory=list)
    stations: List[str] = Field(default_factory=list)
    from_time: Optional[str] = None
    until_time: Optional[str] = None
    expansion: SegmentExpansion


class Effect(BaseModel):
    kind: EffectKind
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    station_codes: List[str] = Field(default_factory=list)
    from_time: Optional[str] = None
    until_time: Optional[str] = None


class ServiceAlteration(BaseModel):
    """A change to one train. ``origin`` and ``destination`` are named from their codes."""

    departs: str
    origin: str
    destination: str
    changes: List[AlterationChange] = Field(default_factory=list)
    retimed_to: Optional[str] = None
    bus_departs: Optional[str] = None
    origin_codes: List[str] = Field(default_factory=list)
    destination_codes: List[str] = Field(default_factory=list)
    station_codes: List[str] = Field(default_factory=list)


class Extraction(BaseModel):
    status: ExtractionStatus
    extractor: Optional[str] = None
    rejected: int = 0


class Revision(BaseModel):
    build: datetime
    seen_at: datetime
    content_hash: str
    trim: bool
    extended: bool = False
    summary: str

    @property
    @deprecated("Revision.html is always None: railworks /v2 no longer republishes Iarnród Éireann's text.")
    def html(self) -> Optional[str]:
        """Deprecated: always None. /v2 doesn't serve the upstream HTML."""
        return None


class WorksNotice(BaseModel):
    """A Works Notice, as /v2 publishes it: facts and railworks' own wording.

    ``title`` and ``summary`` are generated from the facts and may be reworded
    as the generator improves: display them, don't parse them. Use ``days``,
    ``starts_on`` and ``ends_on`` for dates.
    """

    id: str
    service_group: str
    status: NoticeStatus
    withdrawn_reason: Optional[WithdrawnReason] = None
    title: str
    summary: List[str] = Field(default_factory=list)
    days: List[date]
    starts_on: date
    ends_on: date
    until: date
    date_inference: DateInference
    first_seen: datetime
    last_seen: datetime
    revision_count: int
    works_segments: List[WorksSegment] = Field(default_factory=list)
    effects: List[Effect] = Field(default_factory=list)
    stations: List[str] = Field(default_factory=list)
    confidence: float
    extraction: Extraction
    day_sections: Optional[List[DaySection]] = None
    alterations: Optional[List[ServiceAlteration]] = None
    revisions: Optional[List[Revision]] = None

    @property
    @deprecated("WorksNotice.heading is now WorksNotice.title (railworks /v2 no longer republishes Iarnród Éireann's text).")
    def heading(self) -> str:
        """Deprecated alias of ``title``."""
        return self.title

    @property
    @deprecated("WorksNotice.detail is now WorksNotice.summary, a list of lines (railworks /v2 no longer republishes Iarnród Éireann's text).")
    def detail(self) -> Optional[str]:
        """Deprecated: ``summary``'s lines joined with newlines."""
        return "\n".join(self.summary)


class ChangeEvent(BaseModel):
    cursor: str
    type: ChangeEventType
    notice_id: str
    build: datetime
    at: datetime
    trim: Optional[bool] = None
    extended: Optional[bool] = None
    withdrawn_reason: Optional[WithdrawnReason] = None


class StationLine(BaseModel):
    line: str
    position: int


class Station(BaseModel):
    code: str
    name: str
    names: List[str] = Field(default_factory=list)
    alias_codes: List[str] = Field(default_factory=list)
    lat: float
    lon: float
    lines: List[StationLine] = Field(default_factory=list)


class StationSummary(BaseModel):
    code: str
    name: str


class TimeScope(BaseModel):
    from_: Optional[str] = Field(None, alias="from")
    until: Optional[str] = None


class StationDay(BaseModel):
    date: date
    effect: EffectKind
    time_scope: Optional[TimeScope] = None
    notices: List[str] = Field(default_factory=list)


class NoticeRef(BaseModel):
    """A notice named in Health, by its generated ``title``."""

    id: str
    service_group: str
    title: str

    @property
    @deprecated("NoticeRef.heading is now NoticeRef.title (railworks /v2 no longer republishes Iarnród Éireann's text).")
    def heading(self) -> str:
        """Deprecated alias of ``title``."""
        return self.title


class HeldNoticeRef(NoticeRef):
    reason: Optional[HeldReason] = None


class LowConfidenceNoticeRef(NoticeRef):
    confidence: Optional[float] = None


class NeedsReviewNoticeRef(NoticeRef):
    confidence: float
    reasons: List[ReviewReason] = Field(default_factory=list)


class LastFailure(BaseModel):
    at: datetime
    error: str


class HealthExtraction(BaseModel):
    extractor: Optional[str] = None
    pending: int = 0
    failed: int = 0
    last_error: str = ""


class Health(BaseModel):
    source: Source
    last_failure: Optional[LastFailure] = None
    held_notices: List[HeldNoticeRef] = Field(default_factory=list)
    graph_removals: List[List[str]] = Field(default_factory=list)
    unmapped_groups: List[str] = Field(default_factory=list)
    low_confidence: List[LowConfidenceNoticeRef] = Field(default_factory=list)
    needs_review: List[NeedsReviewNoticeRef] = Field(default_factory=list)
    empty_detail: int = 0
    no_stations: int = 0
    unresolved_names: List[dict[str, Any]] = Field(default_factory=list)
    extraction: HealthExtraction


# Response wrapper envelopes
class NoticesResponse(BaseModel):
    source: Source
    notices: List[WorksNotice]


class NoticeResponse(BaseModel):
    source: Source
    notice: WorksNotice


class RawNoticeResponse(BaseModel):
    """What the deprecated ``get_notice_raw()`` returns: a notice's revisions (no HTML)."""

    source: Source
    revisions: List[Revision]


class ChangesResponse(BaseModel):
    source: Source
    events: List[ChangeEvent]
    next: str


class StationsResponse(BaseModel):
    source: Source
    stations: List[Station]


class StationResponse(BaseModel):
    source: Source
    station: Station


class StationDaysResponse(BaseModel):
    source: Source
    station: StationSummary
    days: List[StationDay]
