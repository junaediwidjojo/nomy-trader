"""Quota-accounted FMP discovery. A loser is a candidate, never a buy signal."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine

from nomy_trader.providers.fmp import FmpClient, Loser
from nomy_trader.storage import schema
from nomy_trader.storage.quota import QuotaWindow, reserve

from .universe import ManualUniverse, shortlist


def discover_biggest_losers(
    engine: Engine,
    client: FmpClient,
    quota_window: QuotaWindow,
    now: datetime,
    manual_universe: ManualUniverse | None = None,
) -> tuple[Loser, ...]:
    """Reserve the discovery call, retrieve candidates, then persist the result.

    Reservation happens first and is intentionally retained when FMP fails. The
    durable scan record is only evidence of a successful FMP response; it does
    not state that any candidate passed policy, analysis, or sizing checks.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("discovery clock must be timezone-aware")
    now = now.astimezone(UTC)
    reservation_id = reserve(engine, quota_window, now)
    losers = client.biggest_losers()
    candidates = shortlist(losers, manual_universe) if manual_universe else losers
    payload = {
        "kind": "fmp_biggest_losers",
        "reservation_id": reservation_id,
        "raw_candidate_count": len(losers),
        "candidate_count": len(candidates),
        "raw_candidates": [item.model_dump(mode="json") for item in losers],
        "candidates": [item.model_dump(mode="json") for item in candidates],
        "interpretation": "potential candidates only; not eligibility or a buy signal",
    }
    if manual_universe:
        payload["manual_universe"] = {
            "revision": manual_universe.revision,
            "reviewed_at": manual_universe.reviewed_at.isoformat(),
            "policy": manual_universe.policy.model_dump(mode="json"),
            "limitation": manual_universe.limitation,
        }
    with engine.begin() as connection:
        connection.execute(
            schema.scan_runs.insert().values(
                id=str(uuid4()),
                started_at=now.isoformat(),
                payload=json.dumps(payload),
            )
        )
    return candidates
