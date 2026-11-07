"""Exception and warning classes for pyrailworks."""
from datetime import datetime
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


class GoneError(ProblemError):
    """410 Gone: a retired route (e.g. a /v1 route after its Sunset).

    ``successor`` is the URL the API says to use instead, when it names one.
    """

    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        type_: Optional[str] = None,
        successor: Optional[str] = None,
    ) -> None:
        self.successor = successor
        super().__init__(status=status, title=title, detail=detail, type_=type_)


class ApiDeprecationWarning(FutureWarning):
    """The API marked a route this client called as deprecated.

    Raised as a warning (never an exception) when a response carries a
    ``Deprecation`` (RFC 9745) or ``Sunset`` (RFC 8594) header. It's a
    ``FutureWarning``, so Python shows it by default: the route will stop
    working on ``sunset``, which usually means upgrading pyrailworks.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str,
        deprecated_at: Optional[datetime] = None,
        sunset: Optional[datetime] = None,
        successor: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.deprecated_at = deprecated_at
        self.sunset = sunset
        self.successor = successor
