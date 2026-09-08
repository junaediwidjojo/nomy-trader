"""Persisted FMP quote/history rechecks for discovered candidates."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine

from nomy_trader.providers.fmp import DailyBar, FmpClient, Quote
from nomy_trader.storage import schema
from nomy_trader.storage.quota import QuotaWindow, reserve


class CandidateRecheck(BaseModel):
    """Facts for later eligibility and evidence review, never a buy signal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1)
    checked_at: datetime
    quote: Quote
    history: tuple[DailyBar, ...]


def recheck_candidate(
    engine: Engine,
    client: FmpClient,
    quota_window: QuotaWindow,
    now: datetime,
    symbol: str,
    cache_expires_at: datetime,
) -> CandidateRecheck:
    """Fetch and preserve recheck facts after reserving each FMP request.

    The caller chooses cache expiry because its policy remains unresolved. FMP
    requests that fail still consume their pre-reserved quota allocation.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("recheck clock must be timezone-aware")
    if cache_expires_at.tzinfo is None or cache_expires_at.utcoffset() is None:
        raise ValueError("cache expiry must be timezone-aware")
    now = now.astimezone(UTC)
    cache_expires_at = cache_expires_at.astimezone(UTC)
    if cache_expires_at <= now:
        raise ValueError("cache expiry must follow recheck time")
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("symbol is required")
    quote_reservation = reserve(engine, quota_window, now)
    quote = client.quote(symbol)
    history_reservation = reserve(engine, quota_window, now)
    history = client.daily_history(symbol)
    if quote.symbol != symbol or any(bar.symbol != symbol for bar in history):
        raise ValueError("FMP recheck symbol does not match requested candidate")
    result = CandidateRecheck(
        symbol=symbol, checked_at=now, quote=quote, history=history
    )
    with engine.begin() as connection:
        for cache_key, source_as_of, reservation_id, payload in (
            (
                f"fmp:quote:{symbol}",
                quote.as_of.isoformat(),
                quote_reservation,
                quote.model_dump(mode="json"),
            ),
            (
                f"fmp:history:{symbol}",
                history[0].date,
                history_reservation,
                [bar.model_dump(mode="json") for bar in history],
            ),
        ):
            connection.execute(
                schema.cache.insert().values(
                    id=str(uuid4()),
                    cache_key=cache_key,
                    source_as_of=source_as_of,
                    retrieved_at=now.isoformat(),
                    expires_at=cache_expires_at.isoformat(),
                    payload=json.dumps(
                        {"reservation_id": reservation_id, "data": payload}
                    ),
                )
            )
    return result
