from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa

from nomy_trader.market.discovery import discover_biggest_losers
from nomy_trader.market.universe import load_manual_universe
from nomy_trader.providers.fmp import FmpClient, FmpRateLimitError
from nomy_trader.scenarios import AT
from nomy_trader.storage import schema
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.quota import QuotaExhausted, QuotaWindow


def window() -> QuotaWindow:
    return QuotaWindow(
        id="window-1",
        budget_name="fmp",
        starts_at=AT,
        ends_at=AT + timedelta(days=1),
        call_limit=2,
    )


def fmp(status: int = 200, requests: list[httpx.Request] | None = None) -> FmpClient:
    def transport(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return httpx.Response(
            status,
            json=[
                {
                    "symbol": "ABC",
                    "name": "Example",
                    "price": 10,
                    "change": -2,
                    "changesPercentage": -16.7,
                    "exchange": "NASDAQ",
                }
            ],
            request=request,
        )

    return FmpClient("test-key", httpx.Client(transport=httpx.MockTransport(transport)))


def test_discovery_reserves_and_logs_candidates(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    results = discover_biggest_losers(engine, fmp(), window(), AT)
    assert results[0].symbol == "ABC"
    with engine.connect() as connection:
        payload = connection.execute(sa.select(schema.scan_runs.c.payload)).scalar_one()
        reservations = connection.execute(
            sa.select(sa.func.count()).select_from(schema.quota_reservations)
        ).scalar_one()
    assert "potential candidates only" in payload
    assert "ABC" in payload
    assert reservations == 1
    engine.dispose()


def test_rate_limited_fmp_call_keeps_quota_reservation(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    with pytest.raises(FmpRateLimitError):
        discover_biggest_losers(engine, fmp(429), window(), AT)
    with engine.connect() as connection:
        reservations = connection.execute(
            sa.select(sa.func.count()).select_from(schema.quota_reservations)
        ).scalar_one()
        scans = connection.execute(
            sa.select(sa.func.count()).select_from(schema.scan_runs)
        ).scalar_one()
    assert reservations == 1
    assert scans == 0
    engine.dispose()


def test_exhausted_budget_prevents_another_fmp_call(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    seen: list[httpx.Request] = []
    one_call_window = QuotaWindow(
        id="window-1",
        budget_name="fmp",
        starts_at=AT,
        ends_at=AT + timedelta(days=1),
        call_limit=1,
    )
    discover_biggest_losers(engine, fmp(requests=seen), one_call_window, AT)
    with pytest.raises(QuotaExhausted):
        discover_biggest_losers(engine, fmp(requests=seen), one_call_window, AT)
    assert len(seen) == 1
    engine.dispose()


def test_discovery_logs_raw_and_manual_universe_shortlist(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    universe = load_manual_universe(Path("config/large_cap_universe.json"))
    results = discover_biggest_losers(engine, fmp(), window(), AT, universe)
    assert results == ()
    with engine.connect() as connection:
        payload = connection.execute(sa.select(schema.scan_runs.c.payload)).scalar_one()
    assert '"raw_candidate_count": 1' in payload
    assert '"candidate_count": 0' in payload
    assert universe.revision in payload
    engine.dispose()
