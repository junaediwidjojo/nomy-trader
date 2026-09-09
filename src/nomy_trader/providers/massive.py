"""Read-only daily aggregates; no real-time quotes or broker operations."""

import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Self
from zoneinfo import ZoneInfo

import httpx
from pydantic import AliasChoices, Field, ValidationError, model_validator

from nomy_trader.domain.models import Contract, Nonnegative, Positive


class MassiveError(RuntimeError):
    """Sanitized provider failure, with no response body or credential URL."""


class Aggregate(Contract):
    o: Positive
    h: Positive
    low: Positive = Field(alias="l", validation_alias=AliasChoices("l", "low"))
    c: Positive
    v: Nonnegative
    t: int = Field(strict=True, gt=0)
    n: int | None = Field(default=None, ge=0)
    vw: Decimal | None = Field(default=None, allow_inf_nan=False)
    otc: bool = False

    @model_validator(mode="after")
    def prices(self) -> Self:
        if self.low > min(self.o, self.c) or self.h < max(self.o, self.c):
            raise ValueError("inconsistent OHLC prices")
        return self

    @property
    def session_date(self) -> date:
        return (
            datetime.fromtimestamp(self.t / 1000, UTC)
            .astimezone(ZoneInfo("America/New_York"))
            .date()
        )


class AggregateResponse(Contract):
    ticker: str
    adjusted: Literal[True]
    status: Literal["OK", "DELAYED"]
    results: tuple[Aggregate, ...]
    resultsCount: int = Field(ge=0)
    queryCount: int = Field(ge=0)
    request_id: str
    next_url: str | None = None
    count: int | None = None


class MassiveClient:
    def __init__(
        self,
        api_key: str,
        reserve: Callable[[], object],
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("MASSIVE_API_KEY is required")
        self._key = api_key
        self._reserve = reserve
        self._client = client or httpx.Client(timeout=20, follow_redirects=False)
        self._owns_client = client is None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_client:
            self._client.close()

    def daily_bars(self, symbol: str, start: date, end: date) -> AggregateResponse:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}", symbol):
            raise ValueError("unsupported symbol")
        if not 0 <= (end - start).days <= 365:
            raise ValueError("daily request must cover at most one year")
        self._reserve()
        try:
            response = self._client.get(
                f"https://api.massive.com/v2/aggs/ticker/{symbol}/range/1/day/"
                f"{start.isoformat()}/{end.isoformat()}",
                params={"adjusted": "true", "sort": "asc", "limit": 50000},
                headers={"Authorization": f"Bearer {self._key}"},
            )
        except httpx.HTTPError:
            raise MassiveError("Massive connection failed or timed out") from None
        if response.status_code != 200:
            raise MassiveError(f"Massive returned HTTP {response.status_code}")
        try:
            result = AggregateResponse.model_validate(response.json())
        except (ValueError, ValidationError):
            raise MassiveError("Massive returned unsupported daily data") from None
        if result.ticker != symbol or not result.results:
            raise MassiveError("Massive returned no matching daily bars")
        if result.next_url:
            # Daily requests are bounded to one year; pagination is unexpected.
            raise MassiveError("Massive response incomplete; pagination not followed")
        dates = [bar.session_date for bar in result.results]
        if (
            result.resultsCount != len(dates)
            or dates != sorted(set(dates))
            or dates[0] < start
            or dates[-1] > end
        ):
            raise MassiveError("Massive daily bars have inconsistent dates/count")
        return result
