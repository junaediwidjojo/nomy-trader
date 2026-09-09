"""Quota-reserved raw daily declines for the manual large-cap universe."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Engine

from nomy_trader.domain.models import Contract, Finite, Positive, Text, Timestamp
from nomy_trader.providers.fmp import DailyBar, FmpClient, FmpError
from nomy_trader.storage import schema
from nomy_trader.storage.quota import QuotaWindow, reserve

from .sessions import completed_session
from .universe import ManualUniverse


class DailyDecline(Contract):
    symbol: Text
    session: date
    previous_session: date
    close: Positive
    previous_close: Positive
    volume: Decimal
    return_fraction: Finite
    source: str = "fmp_eod_history"


class UniverseScan(Contract):
    checked_at: Timestamp
    expected_session: date
    universe_revision: Text
    observations: tuple[DailyDecline, ...]
    rejected_symbols: tuple[Text, ...]
    limitation: str = (
        "Raw end-of-day returns only; no decline threshold, liquidity, evidence, "
        "eligibility, plan, or notification"
    )


def scan_daily_declines(
    engine: Engine,
    client: FmpClient,
    quota_window: QuotaWindow,
    now: datetime,
    universe: ManualUniverse,
    max_symbols: int,
) -> UniverseScan:
    """Fetch a bounded prefix and refuse stale or incomplete daily histories."""
    if not isinstance(max_symbols, int) or max_symbols <= 0:
        raise ValueError("max_symbols must be a positive integer")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("scan clock must be timezone-aware")
    now = now.astimezone(UTC)
    expected_session, _ = completed_session(now)
    observations: list[DailyDecline] = []
    rejected: list[str] = []
    for security in universe.securities[:max_symbols]:
        reserve(engine, quota_window, now)
        try:
            observation = _daily_decline(
                security.symbol, client.daily_history(security.symbol)
            )
            if observation.session != expected_session:
                raise ValueError(
                    "history does not include the latest completed session"
                )
            observations.append(observation)
        except (FmpError, ValueError):
            # A failed attempt remains quota-accounted; persist only its symbol.
            rejected.append(security.symbol)
    result = UniverseScan(
        checked_at=now,
        expected_session=expected_session,
        universe_revision=universe.revision,
        observations=tuple(observations),
        rejected_symbols=tuple(rejected),
    )
    payload = {
        "kind": "manual_universe_daily_declines",
        **result.model_dump(mode="json"),
    }
    with engine.begin() as connection:
        connection.execute(
            schema.scan_runs.insert().values(
                id=str(uuid4()), started_at=now.isoformat(), payload=json.dumps(payload)
            )
        )
    return result


def _daily_decline(symbol: str, bars: tuple[DailyBar, ...]) -> DailyDecline:
    by_date = {date.fromisoformat(bar.date): bar for bar in bars}
    sessions = sorted(by_date, reverse=True)
    if len(sessions) < 2:
        raise ValueError("daily history has fewer than two sessions")
    latest_date, previous_date = sessions[:2]
    latest, previous = by_date[latest_date], by_date[previous_date]
    return DailyDecline(
        symbol=symbol,
        session=latest_date,
        previous_session=previous_date,
        close=latest.price,
        previous_close=previous.price,
        volume=latest.volume,
        return_fraction=latest.price / previous.price - 1,
    )
