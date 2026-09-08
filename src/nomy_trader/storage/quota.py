"""Reserve before every request; failures and ambiguous requests are not refunded."""

from datetime import UTC, datetime
from typing import Self
from uuid import uuid4

import sqlalchemy as sa
from pydantic import model_validator
from sqlalchemy import Engine

from nomy_trader.domain.models import Contract, Days, Text, Timestamp

from .schema import quota_reservations, quota_windows


class QuotaWindow(Contract):
    id: Text
    budget_name: Text
    starts_at: Timestamp
    ends_at: Timestamp
    call_limit: Days

    @model_validator(mode="after")
    def chronology(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("quota reset must follow window start")
        return self


class QuotaExhausted(ValueError):
    pass


def reserve(engine: Engine, window: QuotaWindow, now: datetime, calls: int = 1) -> str:
    """Account boundary is explicit; provider reset semantics are not assumed.

    Use one stable budget_name for all FMP consumers. Every retry needs a new
    reservation. A crash after reservation conservatively consumes those calls.
    """
    if isinstance(calls, bool) or not isinstance(calls, int) or calls <= 0:
        raise ValueError("positive integer call cost required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("quota clock must be timezone-aware")
    now = now.astimezone(UTC)
    if not window.starts_at <= now < window.ends_at:
        raise ValueError("clock outside quota window")
    values = dict(
        id=window.id,
        budget_name=window.budget_name,
        starts_at=window.starts_at.isoformat(),
        ends_at=window.ends_at.isoformat(),
        call_limit=window.call_limit,
    )
    with engine.connect() as conn:
        # Serialize the read/check/write even if two local callers race.
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            existing = (
                conn.execute(
                    sa.select(quota_windows).where(
                        quota_windows.c.id == window.id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None and dict(existing) != values:
                raise ValueError("quota window configuration changed")
            if existing is None:
                overlap = conn.execute(
                    sa.select(quota_windows.c.id).where(
                        quota_windows.c.budget_name == window.budget_name,
                        quota_windows.c.starts_at < values["ends_at"],
                        quota_windows.c.ends_at > values["starts_at"],
                    )
                ).first()
                if overlap is not None:
                    raise ValueError("overlapping quota window would reset usage")
                conn.execute(quota_windows.insert().values(**values))
            used = conn.execute(
                sa.select(
                    sa.func.coalesce(
                        sa.func.sum(quota_reservations.c.calls),
                        0,
                    )
                ).where(quota_reservations.c.window_id == window.id)
            ).scalar_one()
            if int(used) + calls > window.call_limit:
                raise QuotaExhausted("daily request budget exhausted")
            identity = str(uuid4())
            conn.execute(
                quota_reservations.insert().values(
                    id=identity,
                    window_id=window.id,
                    reserved_at=now.isoformat(),
                    calls=calls,
                )
            )
            conn.commit()
            return identity
        except BaseException:
            conn.rollback()
            raise
