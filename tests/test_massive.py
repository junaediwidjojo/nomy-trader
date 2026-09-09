import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from nomy_trader.providers.massive import MassiveClient, MassiveError
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.rate_limit import RateLimited, reserve_credits, reserve_request

AT = datetime(2026, 9, 8, 12, tzinfo=UTC)


def payload():
    return {
        "ticker": "BANL",
        "adjusted": True,
        "status": "OK",
        "resultsCount": 1,
        "queryCount": 1,
        "request_id": "fixture",
        "results": [
            {
                "o": 10,
                "h": 11,
                "l": 8,
                "c": 9,
                "v": 1000,
                "t": int(datetime(2026, 9, 4, 4, tzinfo=UTC).timestamp() * 1000),
            }
        ],
    }


def test_adapter_auth_and_rate_reservation():
    calls = []

    def send(request):
        assert calls == ["reserved"]
        assert request.headers["Authorization"] == "Bearer private-key"
        assert "private-key" not in str(request.url)
        return httpx.Response(200, json=payload())

    with MassiveClient(
        "private-key",
        lambda: calls.append("reserved"),
        httpx.Client(transport=httpx.MockTransport(send)),
    ) as client:
        result = client.daily_bars("BANL", date(2026, 9, 1), date(2026, 9, 4))
        assert result.results[0].session_date == date(2026, 9, 4)


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500, 302])
def test_http_errors_sanitized(status):
    def send(request):
        return httpx.Response(status, text="private-key")

    client = MassiveClient(
        "private-key", lambda: None, httpx.Client(transport=httpx.MockTransport(send))
    )
    with pytest.raises(MassiveError) as error:
        client.daily_bars("BANL", date(2026, 9, 1), date(2026, 9, 4))
    assert "private-key" not in str(error.value)


@pytest.mark.parametrize(
    "update",
    [
        {"ticker": "OTHER"},
        {"results": []},
        {"adjusted": False},
        {"next_url": "https://untrusted.invalid"},
        {"resultsCount": 2},
        {"results": [{"c": 10}]},
        {"status": "ERROR"},
    ],
)
def test_bad_data_rejected(update):
    client = MassiveClient(
        "private-key",
        lambda: None,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        **payload(),
                        **update,
                    },
                )
            )
        ),
    )
    with pytest.raises(MassiveError):
        client.daily_bars("BANL", date(2026, 9, 1), date(2026, 9, 4))


def test_timeout_does_not_chain_secret_exception():
    def send(request):
        raise httpx.ReadTimeout("private-key")

    client = MassiveClient(
        "private-key", lambda: None, httpx.Client(transport=httpx.MockTransport(send))
    )
    with pytest.raises(MassiveError) as error:
        client.daily_bars("BANL", date(2026, 9, 1), date(2026, 9, 4))
    assert "private-key" not in "".join(traceback.format_exception(error.value))


def test_rolling_rate_survives_restart_and_boundary(tmp_path):
    path = tmp_path / "rate.sqlite"
    engine = open_database(path)
    upgrade(engine)
    for _ in range(5):
        reserve_request(engine, "massive", AT)
    engine.dispose()
    engine = open_database(path)
    with pytest.raises(RateLimited):
        reserve_request(engine, "massive", AT + timedelta(seconds=59))
    with pytest.raises(RateLimited):
        reserve_request(engine, "massive", AT - timedelta(seconds=1))
    reserve_request(engine, "massive", AT + timedelta(seconds=60))
    engine.dispose()


def test_rolling_rate_serializes_competing_callers(tmp_path):
    engine = open_database(tmp_path / "rate.sqlite")
    upgrade(engine)

    def attempt(_):
        try:
            reserve_request(engine, "massive", AT)
            return True
        except RateLimited:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(12))) == 5
    engine.dispose()


def test_twelve_data_credit_budgets_are_persistent(tmp_path):
    engine = open_database(tmp_path / "rate.sqlite")
    upgrade(engine)
    reserve_credits(engine, "twelve_data", AT, credits=7)
    reserve_credits(engine, "twelve_data", AT, credits=1)
    with pytest.raises(RateLimited):
        reserve_credits(engine, "twelve_data", AT, credits=1)
    reserve_credits(engine, "twelve_data", AT + timedelta(seconds=60), credits=8)
    with pytest.raises(ValueError):
        reserve_credits(engine, "twelve_data", AT, credits=0)
    engine.dispose()
