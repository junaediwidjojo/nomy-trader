from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from nomy_trader.scenarios import AT
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.quota import QuotaExhausted, QuotaWindow, reserve


def window(**updates):
    return QuotaWindow.model_validate(
        {
            "id": "day-1",
            "budget_name": "fmp",
            "starts_at": AT,
            "ends_at": AT + timedelta(days=1),
            "call_limit": 2,
            **updates,
        }
    )


def test_restart_and_explicit_reset(tmp_path):
    path = tmp_path / "journal.sqlite"
    engine = open_database(path)
    upgrade(engine, "001")
    upgrade(engine)
    reserve(engine, window(), AT)
    engine.dispose()
    engine = open_database(path)
    reserve(engine, window(), AT)
    with pytest.raises(QuotaExhausted):
        reserve(engine, window(), AT)
    with pytest.raises(ValueError):
        reserve(engine, window(id="new-id"), AT)
    with pytest.raises(ValueError):
        reserve(engine, window(call_limit=100), AT)
    with pytest.raises(ValueError):
        reserve(engine, window(), AT + timedelta(days=1))
    next_window = window(
        id="day-2", starts_at=AT + timedelta(days=1), ends_at=AT + timedelta(days=2)
    )
    reserve(engine, next_window, AT + timedelta(days=1))
    engine.dispose()


def test_concurrent_reservations_cannot_overspend(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)

    def attempt(_):
        try:
            reserve(engine, window(), AT)
            return True
        except QuotaExhausted:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(attempt, range(8))) == 2
    engine.dispose()


@pytest.mark.parametrize("calls", [0, -1, True, 1.5])
def test_invalid_cost_rejected(tmp_path, calls):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    with pytest.raises(ValueError):
        reserve(engine, window(), AT, calls=calls)
    engine.dispose()
