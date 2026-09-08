from datetime import timedelta

import httpx
import pytest
import sqlalchemy as sa

from nomy_trader.market.recheck import recheck_candidate
from nomy_trader.providers.fmp import FmpClient, FmpError
from nomy_trader.scenarios import AT
from nomy_trader.storage import schema
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.quota import QuotaWindow


def window(limit: int = 3) -> QuotaWindow:
    return QuotaWindow(
        id="window-1",
        budget_name="fmp",
        starts_at=AT,
        ends_at=AT + timedelta(days=1),
        call_limit=limit,
    )


def fmp(wrong_symbol: bool = False, history_status: int = 200) -> FmpClient:
    def transport(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/quote"):
            payload = [
                {
                    "symbol": "WRONG" if wrong_symbol else "ABC",
                    "name": "Example",
                    "price": 10,
                    "previousClose": 12,
                    "marketCap": 1000000,
                    "volume": 5000,
                    "timestamp": 1778270400,
                }
            ]
            return httpx.Response(200, json=payload, request=request)
        return httpx.Response(
            history_status,
            json=[{"symbol": "ABC", "date": "2026-05-08", "price": 10, "volume": 5000}],
            request=request,
        )

    return FmpClient("test-key", httpx.Client(transport=httpx.MockTransport(transport)))


def test_recheck_reserves_two_calls_and_caches_facts(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    result = recheck_candidate(
        engine, fmp(), window(), AT, " abc ", AT + timedelta(minutes=5)
    )
    assert result.symbol == "ABC"
    assert result.quote.volume == 5000
    with engine.connect() as connection:
        caches = connection.execute(
            sa.select(sa.func.count()).select_from(schema.cache)
        ).scalar_one()
        reservations = connection.execute(
            sa.select(sa.func.count()).select_from(schema.quota_reservations)
        ).scalar_one()
    assert caches == 2
    assert reservations == 2
    engine.dispose()


def test_history_failure_keeps_both_reservations_without_cache(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    with pytest.raises(FmpError):
        recheck_candidate(
            engine,
            fmp(history_status=500),
            window(),
            AT,
            "ABC",
            AT + timedelta(minutes=5),
        )
    with engine.connect() as connection:
        caches = connection.execute(
            sa.select(sa.func.count()).select_from(schema.cache)
        ).scalar_one()
        reservations = connection.execute(
            sa.select(sa.func.count()).select_from(schema.quota_reservations)
        ).scalar_one()
    assert caches == 0
    assert reservations == 2
    engine.dispose()


def test_recheck_rejects_symbol_mismatch_and_expired_cache(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    with pytest.raises(ValueError):
        recheck_candidate(
            engine,
            fmp(wrong_symbol=True),
            window(),
            AT,
            "ABC",
            AT + timedelta(minutes=5),
        )
    with pytest.raises(ValueError):
        recheck_candidate(engine, fmp(), window(), AT, "ABC", AT)
    engine.dispose()
