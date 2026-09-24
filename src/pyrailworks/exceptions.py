"""Exception classes for pyrailworks."""
from typing import Optional


class RailworksError(Exception):
    """Base exception for all railworks errors."""


class ProblemError(RailworksError):
    """RFC 9457 Problem Details error returned by the Railworks API."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        type_: Optional[str] = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_
        super().__init__(f"[{status}] {title}: {detail}")


class BadRequestError(ProblemError):
    """400 Bad Request: bad or unknown query parameter."""


class NotFoundError(ProblemError):
    """404 Not Found: no such notice, station or resource."""


class StationsLoadingError(ProblemError):
    """503 Service Unavailable: station list hasn't loaded yet."""
