from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

from nomy_trader.market.universe import load_manual_universe
from nomy_trader.market.universe_scan import scan_daily_declines
from nomy_trader.providers.fmp import FmpClient
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.quota import QuotaWindow

NOW = datetime(2026, 9, 9, 14, tzinfo=UTC)


def client(latest: str = "2026-09-08") -> FmpClient:
    def send(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params["symbol"]
        return httpx.Response(
            200,
            json=[
                {"symbol": symbol, "date": latest, "price": 90, "volume": 1000},
                {"symbol": symbol, "date": "2026-09-05", "price": 100, "volume": 900},
            ],
        )

    return FmpClient("test-key", httpx.Client(transport=httpx.MockTransport(send)))


def window() -> QuotaWindow:
    return QuotaWindow(
        id="fmp-universe",
        budget_name="fmp-universe",
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(days=1),
        call_limit=3,
    )


def test_raw_declines_are_quota_accounted_and_persisted(tmp_path):
    engine = open_database(tmp_path / "scan.sqlite")
    upgrade(engine)
    universe = load_manual_universe(Path("config/large_cap_universe.json"))
    result = scan_daily_declines(
        engine, client(), window(), NOW, universe, max_symbols=2
    )
    assert len(result.observations) == 2
    assert result.observations[0].return_fraction == Decimal("-0.1")
    assert result.rejected_symbols == ()
    engine.dispose()


def test_stale_history_is_rejected_and_recorded(tmp_path):
    engine = open_database(tmp_path / "scan.sqlite")
    upgrade(engine)
    universe = load_manual_universe(Path("config/large_cap_universe.json"))
    result = scan_daily_declines(
        engine, client("2026-09-04"), window(), NOW, universe, max_symbols=1
    )
    assert result.observations == ()
    assert result.rejected_symbols == ("AAPL",)
    engine.dispose()
