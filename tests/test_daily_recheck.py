from datetime import UTC, datetime, timedelta

import pytest

from nomy_trader.market.daily_recheck import recheck_daily
from nomy_trader.market.sessions import completed_session
from nomy_trader.providers.massive import AggregateResponse, MassiveError
from nomy_trader.storage.database import open_database, upgrade

NOW = datetime(2026, 9, 9, 5, tzinfo=UTC)


def payload(last_session: str) -> AggregateResponse:
    timestamps = {"2026-09-04": 1788494400000, "2026-09-08": 1788840000000}
    results = [
        {"o": 10, "h": 11, "l": 8, "c": 9, "v": 1000, "t": timestamps["2026-09-04"]},
        {"o": 9, "h": 10, "l": 7, "c": 8, "v": 2000, "t": timestamps[last_session]},
    ]
    return AggregateResponse.model_validate(
        {
            "ticker": "BANL",
            "adjusted": True,
            "status": "OK",
            "results": results,
            "resultsCount": len(results),
            "queryCount": len(results),
            "request_id": "test",
        }
    )


class Client:
    def __init__(self, response: AggregateResponse) -> None:
        self.response = response
        self.calls = 0

    def daily_bars(self, symbol, start, end):
        self.calls += 1
        return self.response


def test_completed_session_handles_weekend_and_premarket():
    session, expiry = completed_session(NOW)
    assert session.isoformat() == "2026-09-08"
    assert expiry == datetime(2026, 9, 9, 20, tzinfo=UTC)


def test_daily_recheck_persists_only_latest_completed_session(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    client = Client(payload("2026-09-08"))
    result = recheck_daily(engine, client, "BANL", NOW)
    assert result.bars.results[-1].session_date.isoformat() == "2026-09-08"
    assert client.calls == 1
    # The same session is cached until the next exchange close.
    assert recheck_daily(engine, client, "BANL", NOW + timedelta(minutes=5)) == result
    assert client.calls == 1
    engine.dispose()


def test_stale_daily_data_is_rejected_and_logged(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    client = Client(payload("2026-09-04"))
    with pytest.raises(MassiveError, match="latest completed session"):
        recheck_daily(engine, client, "BANL", NOW)
    engine.dispose()
