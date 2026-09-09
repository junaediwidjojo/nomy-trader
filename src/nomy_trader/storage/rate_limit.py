"""Persistent rolling-window reservations, including failed attempts."""

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Engine

from .schema import provider_requests


class RateLimited(ValueError):
    pass


def reserve_request(engine: Engine, provider: str, now: datetime) -> str:
    """Reserve one provider credit/request."""
    return reserve_credits(engine, provider, now, credits=1)


def reserve_credits(engine: Engine, provider: str, now: datetime, credits: int) -> str:
    """Fixed provider ceilings; serialize callers across process restarts.

    FMP uses a conservative rolling 24 hours until its reset boundary is known.
    Massive uses five requests in any rolling minute. Twelve Data Basic has
    eight credits/minute and 800/day. No automatic retry here.
    """
    limits = {
        "massive": ((5, 60),),
        "fmp": ((250, 86400),),
        "twelve_data": ((8, 60), (800, 86400)),
    }
    if provider not in limits:
        raise ValueError("unsupported provider budget")
    if not isinstance(credits, int) or credits <= 0:
        raise ValueError("credits must be a positive integer")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("rate clock must be aware")
    timestamp = now.timestamp()
    with engine.connect() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            latest = conn.execute(
                sa.select(sa.func.max(provider_requests.c.reserved_at)).where(
                    provider_requests.c.provider == provider
                )
            ).scalar_one()
            if latest is not None and timestamp < latest:
                raise RateLimited("clock moved backwards; requests paused")
            for limit, duration in limits[provider]:
                used = conn.execute(
                    sa.select(sa.func.count()).where(
                        provider_requests.c.provider == provider,
                        provider_requests.c.reserved_at > timestamp - duration,
                    )
                ).scalar_one()
                if used + credits > limit:
                    raise RateLimited(
                        f"{provider} request allowance exhausted; retry later"
                    )
            identity = str(uuid4())
            conn.execute(
                provider_requests.insert(),
                [
                    {
                        "id": identity if index == 0 else str(uuid4()),
                        "provider": provider,
                        "reserved_at": timestamp,
                    }
                    for index in range(credits)
                ],
            )
            conn.commit()
            return identity
        except BaseException:
            conn.rollback()
            raise
