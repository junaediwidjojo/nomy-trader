"""Read-only Twelve Data quote adapter for bounded candidate rechecks."""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class TwelveDataError(RuntimeError):
    """Sanitized provider failure safe for local logs."""


class TwelveDataRateLimitError(TwelveDataError):
    """The provider rejected a request due to its credit limit."""


class Quote(BaseModel):
    """Minimal provider quote; extra fields are intentionally ignored."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
    timestamp: int = Field(gt=0)
    close: Decimal = Field(gt=0, allow_inf_nan=False)
    previous_close: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: Decimal = Field(ge=0, allow_inf_nan=False)

    @property
    def as_of(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp, UTC)


class TwelveDataClient:
    """Small injectable client. Authentication uses a header, never a URL."""

    base_url = "https://api.twelvedata.com"

    def __init__(
        self,
        api_key: str,
        reserve_credits: Callable[[int], object],
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("TWELVE_DATA_API_KEY is required")
        self._key = api_key
        self._reserve_credits = reserve_credits
        self._client = client or httpx.Client(timeout=20, follow_redirects=False)
        self._owns_client = client is None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_client:
            self._client.close()

    def quote(self, symbol: str) -> Quote:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}", symbol):
            raise ValueError("unsupported symbol")
        # The published /quote endpoint weight is one credit per symbol.
        self._reserve_credits(1)
        try:
            response = self._client.get(
                f"{self.base_url}/quote",
                params={"symbol": symbol},
                headers={"Authorization": f"apikey {self._key}"},
            )
        except httpx.HTTPError:
            raise TwelveDataError(
                "Twelve Data connection failed or timed out"
            ) from None
        if response.status_code == 429:
            raise TwelveDataRateLimitError("Twelve Data credit allowance exhausted")
        if response.status_code != 200:
            raise TwelveDataError(f"Twelve Data returned HTTP {response.status_code}")
        try:
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("status") == "error":
                raise ValueError
            quote = Quote.model_validate(payload)
        except (ValueError, ValidationError):
            raise TwelveDataError(
                "Twelve Data returned unsupported quote data"
            ) from None
        if quote.symbol != symbol:
            raise TwelveDataError("Twelve Data returned a mismatched symbol")
        return quote
