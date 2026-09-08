"""FMP end-of-day market-data adapter.

The adapter is deliberately read-only. It accepts no broker credential and does
not log URLs because FMP authenticates using a query parameter.
"""

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class FmpError(RuntimeError):
    """A sanitized provider failure safe for application logs."""


class FmpAuthError(FmpError):
    """Authentication was rejected without reporting the secret."""


class FmpRateLimitError(FmpError):
    """FMP denied a request due to a rate or daily limit."""


class FmpPayloadError(FmpError):
    """FMP returned a successful but unsupported payload."""


class FmpModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Loser(FmpModel):
    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    change: Decimal = Field(allow_inf_nan=False)
    changesPercentage: Decimal = Field(allow_inf_nan=False)
    exchange: str = Field(min_length=1)


class Quote(FmpModel):
    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    previousClose: Decimal = Field(gt=0, allow_inf_nan=False)
    marketCap: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: Decimal = Field(ge=0, allow_inf_nan=False)
    timestamp: int = Field(gt=0)

    @property
    def as_of(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp, UTC)


class DailyBar(FmpModel):
    symbol: str = Field(min_length=1)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: Decimal = Field(ge=0, allow_inf_nan=False)


class FmpClient:
    """Small FMP stable-API client with injectable transport for tests."""

    base_url = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key.strip():
            raise ValueError("FMP API key is required")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=20.0)
        self._owns_client = client is None

    @classmethod
    def from_environment(cls) -> Self:
        load_dotenv()
        key = os.environ.get("FMP_API_KEY")
        if key is None:
            raise ValueError("FMP_API_KEY is not configured")
        return cls(key)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def biggest_losers(self) -> tuple[Loser, ...]:
        return self._models("/biggest-losers", Loser)

    def quote(self, symbol: str) -> Quote:
        return self._models("/quote", Quote, {"symbol": symbol})[0]

    def daily_history(self, symbol: str) -> tuple[DailyBar, ...]:
        return self._models("/historical-price-eod/light", DailyBar, {"symbol": symbol})

    def _models[T: FmpModel](
        self, path: str, model: type[T], params: dict[str, str] | None = None
    ) -> tuple[T, ...]:
        payload = self._request(path, params)
        if not isinstance(payload, list) or not payload:
            raise FmpPayloadError("FMP returned an empty or non-list payload")
        try:
            return tuple(model.model_validate(item) for item in payload)
        except ValidationError as exc:
            raise FmpPayloadError("FMP response fields are unsupported") from exc

    def _request(self, path: str, params: dict[str, str] | None) -> object:
        query = {"apikey": self._api_key, **(params or {})}
        try:
            response = self._client.get(f"{self.base_url}{path}", params=query)
        except httpx.TimeoutException as exc:
            raise FmpError("FMP request timed out") from exc
        except httpx.HTTPError as exc:
            raise FmpError("FMP request failed") from exc
        if response.status_code in {401, 403}:
            raise FmpAuthError("FMP authentication failed")
        if response.status_code == 429:
            raise FmpRateLimitError("FMP rate limit reached")
        if response.is_error:
            raise FmpError(f"FMP returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise FmpPayloadError("FMP returned invalid JSON") from exc
