import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from scripts.run_tradingagents_single import (
    _install_recent_ohlcv_refresh,
    _merge_recent_ohlcv,
    _pin_tool_dates,
    _restore_reported_close,
)


def test_recent_fetch_restores_missing_latest_close_without_lookahead() -> None:
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-10-19", "2026-10-20"]),
            "Close": [88.47, 80.43],
        }
    )
    recent = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-10-20", "2026-10-21", "2026-10-23"]),
            "Close": [81.0, 77.94, 999.0],
        }
    )
    result = _merge_recent_ohlcv(frame, recent, "2026-10-22")
    assert list(result["Close"]) == [88.47, 80.43, 77.94]
    assert result.iloc[-1]["Date"] == pd.Timestamp("2026-10-21")
    assert len(frame) == 2


def test_unusable_recent_prices_cannot_silently_approve_older_data() -> None:
    frame = pd.DataFrame({"Date": pd.to_datetime(["2026-10-20"]), "Close": [80.43]})
    recent = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-10-21", "2026-10-22"]),
            "Close": [float("nan"), 0.0],
        }
    )
    with pytest.raises(ValueError, match="no usable closing prices"):
        _merge_recent_ohlcv(frame, recent, "2026-10-22")


def test_missing_close_requires_matching_completed_session_and_price_range() -> None:
    recent = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-10-20", "2026-10-21"]),
            "Close": [80.43, float("nan")],
            "High": [86.43, 80.18],
            "Low": [79.89, 75.99],
        }
    )
    meta = {
        "regularMarketTime": pd.Timestamp("2026-10-21 16:00:02", tz="America/New_York"),
        "regularMarketPrice": 77.94,
    }
    result = _restore_reported_close(recent, meta)
    assert result.iloc[-1]["Close"] == 77.94
    assert pd.isna(recent.iloc[-1]["Close"])
    for stamp, price in [
        ("2026-10-21 15:59:00", 77.94),
        ("2026-10-20 16:00:02", 77.94),
        ("2026-10-21 16:00:02", 100.0),
    ]:
        invalid = {
            "regularMarketTime": pd.Timestamp(stamp, tz="America/New_York"),
            "regularMarketPrice": price,
        }
        assert pd.isna(_restore_reported_close(recent, invalid).iloc[-1]["Close"])


def test_refresh_updates_imported_tool_bindings_and_records_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = pd.DataFrame({"Date": pd.to_datetime(["2026-10-20"]), "Close": [80.43]})
    recent = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-10-21"]),
            "Close": [float("nan")],
            "High": [80.18],
            "Low": [75.99],
        }
    ).set_index("Date")
    ticker = SimpleNamespace(
        history=lambda **kwargs: recent,
        history_metadata={
            "regularMarketTime": pd.Timestamp(
                "2026-10-21 16:00:02", tz="America/New_York"
            ),
            "regularMarketPrice": 77.94,
        },
    )

    def original(symbol, curr_date):
        return frame

    stats = SimpleNamespace(
        load_ohlcv=original,
        normalize_symbol=lambda s: s,
        yf=SimpleNamespace(Ticker=lambda symbol: ticker),
        yf_with_timeout=lambda func, seconds: func(),
        _clean_dataframe=lambda d: d,
    )
    package = ModuleType("tradingagents")
    dataflows = ModuleType("tradingagents.dataflows")
    dataflows.stockstats_utils = stats
    tool = SimpleNamespace(load_ohlcv=original)
    for name, module in {
        "tradingagents": package,
        "tradingagents.dataflows": dataflows,
        "tradingagents.dataflows.stockstats_utils": stats,
        "tradingagents.dataflows.market_data_validator": tool,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    observed = {}
    _install_recent_ohlcv_refresh(observed)
    result = tool.load_ohlcv("SE", "2026-10-22")
    assert result.iloc[-1]["Close"] == 77.94
    assert observed["SE@2026-10-22"]["latest_date"] == "2026-10-21"
    result.loc[result.index[-1], "Close"] = 0
    assert tool.load_ohlcv("SE", "2026-10-22").iloc[-1]["Close"] == 77.94


def test_current_run_pins_tool_asof_dates_without_changing_symbol_or_window() -> None:
    def snapshot(symbol, curr_date, look_back_days=30):
        return symbol, curr_date, look_back_days

    tool = SimpleNamespace(name="snapshot", func=snapshot)
    node = SimpleNamespace(tools_by_name={"snapshot": tool})
    graph = SimpleNamespace(tool_nodes={"market": node, "fundamentals": node})
    overrides = []
    _pin_tool_dates(graph, "2026-10-22", overrides)
    assert tool.func("NTES", "2026-10-20", look_back_days=15) == (
        "NTES",
        "2026-10-22",
        15,
    )
    assert len(overrides) == 1
    assert overrides[0]["requested"] == "2026-10-20"
