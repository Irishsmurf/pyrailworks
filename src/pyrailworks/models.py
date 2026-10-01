"""Pydantic data models for the Railworks API."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class OpenEnum(str, Enum):
    """An enum that accepts values it doesn't know yet.

    The Railworks API only makes additive changes within /v1, and its enum
    lists are open: a new effect kind or change-event type may appear without
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
    heading: str
    days: List[date] = Field(default_factory=list)


class WorksSegment(BaseModel):
    clause: str
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    from_codes: List[str] = Field(default_factory=list)
    to_codes: List[str] = Field(default_factory=list)
    stations: List[str] = Field(default_factory=list)
    from_time: Optional[str] = None
    until_time: Optional[str] = None
    expansion: SegmentExpansion
    quote: str


class Effect(BaseModel):
    kind: EffectKind
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    station_codes: List[str] = Field(default_factory=list)
    from_time: Optional[str] = None
    until_time: Optional[str] = None
    quote: str


class ServiceAlteration(BaseModel):
    departs: str
    origin: str
    destination: str
    changes: List[AlterationChange] = Field(default_factory=list)
    stations: List[str] = Field(default_factory=list)
    retimed_to: Optional[str] = None
    bus_departs: Optional[str] = None
    quote: str
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
    summary: str
    html: Optional[str] = None


class WorksNotice(BaseModel):
    id: str
    service_group: str
    status: NoticeStatus
    heading: str
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
    detail: Optional[str] = None
    alterations: Optional[List[ServiceAlteration]] = None
    revisions: Optional[List[Revision]] = None


class ChangeEvent(BaseModel):
    cursor: str
    type: ChangeEventType
    notice_id: str
    build: datetime
    at: datetime
    trim: Optional[bool] = None


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
    id: str
    service_group: str
    heading: str


class LowConfidenceNoticeRef(NoticeRef):
    confidence: Optional[float] = None


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
    held_notices: List[NoticeRef] = Field(default_factory=list)
    graph_removals: List[List[str]] = Field(default_factory=list)
    unmapped_groups: List[str] = Field(default_factory=list)
    low_confidence: List[LowConfidenceNoticeRef] = Field(default_factory=list)
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
