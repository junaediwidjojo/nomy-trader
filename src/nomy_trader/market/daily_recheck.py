"""Massive completed-session observations, persisted without eligibility claims."""

from datetime import datetime, timedelta
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Engine

from nomy_trader.domain.models import Contract, Timestamp
from nomy_trader.providers.massive import AggregateResponse, MassiveClient, MassiveError
from nomy_trader.storage.schema import cache, scan_runs

from .sessions import completed_session


class DailyRecheck(Contract):
    symbol: str
    checked_at: Timestamp
    expires_at: Timestamp
    bars: AggregateResponse
    status: str = "DATA_RECHECKED"
    limitation: str = "Daily price/volume only; eligibility and evidence review pending"


def recheck_daily(
    engine: Engine, client: MassiveClient, symbol: str, now: datetime
) -> DailyRecheck:
    session, expires = completed_session(now)
    key = f"massive:daily-adjusted:{symbol}:{session}"
    with engine.connect() as conn:
        existing = conn.execute(
            sa.select(cache.c.payload)
            .where(
                cache.c.cache_key == key,
            )
            .order_by(cache.c.retrieved_at.desc())
        ).scalar()
    if existing is not None:
        saved = DailyRecheck.model_validate_json(existing)
        if saved.checked_at <= now < saved.expires_at:
            return saved
    try:
        bars = client.daily_bars(symbol, session - timedelta(days=120), session)
        if len(bars.results) < 2 or bars.results[-1].session_date != session:
            raise MassiveError("daily history missing latest completed session")
        result = DailyRecheck(
            symbol=symbol, checked_at=now, expires_at=expires, bars=bars
        )
        with engine.begin() as conn:
            conn.execute(
                cache.insert().values(
                    id=str(uuid4()),
                    cache_key=key,
                    source_as_of=session.isoformat(),
                    retrieved_at=now.isoformat(),
                    expires_at=expires.isoformat(),
                    payload=result.model_dump_json(),
                )
            )
            conn.execute(
                scan_runs.insert().values(
                    id=str(uuid4()),
                    started_at=now.isoformat(),
                    payload=result.model_dump_json(),
                )
            )
        return result
    except MassiveError:
        # No raw provider response, exception chain or key is persisted.
        with engine.begin() as conn:
            conn.execute(
                scan_runs.insert().values(
                    id=str(uuid4()),
                    started_at=now.isoformat(),
                    payload='{"kind":"massive_recheck","status":"PROVIDER_OR_DATA_FAILURE"}',
                )
            )
        raise
