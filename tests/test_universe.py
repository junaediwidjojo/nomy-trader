from pathlib import Path

import pytest

from nomy_trader.market.universe import load_manual_universe, shortlist
from nomy_trader.providers.fmp import Loser


def test_manual_seed_loads_and_filters_price_and_symbols():
    universe = load_manual_universe(Path("config/large_cap_universe.json"))
    results = shortlist(
        (
            Loser(
                symbol="AAPL",
                name="Apple",
                price="10",
                change="-1",
                changesPercentage="-9",
                exchange="NASDAQ",
            ),
            Loser(
                symbol="MSFT",
                name="Microsoft",
                price="9.99",
                change="-1",
                changesPercentage="-9",
                exchange="NASDAQ",
            ),
            Loser(
                symbol="MICRO",
                name="Micro",
                price="100",
                change="-1",
                changesPercentage="-9",
                exchange="NASDAQ",
            ),
        ),
        universe,
    )
    assert [item.symbol for item in results] == ["AAPL"]


@pytest.mark.parametrize(
    "payload",
    [
        '{"revision":"x"}',
        '{"revision":"x","reviewed_at":"2026-09-09T00:00:00Z","reviewer":"x","policy":{"minimum_price_usd":"10","minimum_market_cap_usd":"2"},"limitation":"x","securities":[{"symbol":"AAPL","issuer":"Apple"},{"symbol":"AAPL","issuer":"Apple"}]}',
        '{"revision":"x","reviewed_at":"2026-09-09T00:00:00Z","reviewer":"x","policy":{"minimum_price_usd":"10","minimum_market_cap_usd":"2"},"limitation":"x","securities":[{"symbol":"SPY","issuer":"ETF","security_type":"ETF"}]}',
    ],
)
def test_invalid_manual_universe_fails_closed(tmp_path, payload):
    path = tmp_path / "universe.json"
    path.write_text(payload)
    with pytest.raises(ValueError, match="manual universe file is invalid"):
        load_manual_universe(path)
