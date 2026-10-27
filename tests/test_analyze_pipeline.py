from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from nomy_trader.analysis.bullish import is_bullish_signal, qualifies_on_upside
from nomy_trader.analysis.pipeline import (
    ScreenedSymbol,
    analyze_symbol,
    format_price,
)


def test_analyze_symbol_maps_tradingagents_payload() -> None:
    screened = ScreenedSymbol(
        symbol="FIZZ",
        issuer_name="National Beverage Corp.",
        ajaib_price=Decimal("29.83"),
        one_day_percent=Decimal("-3.65"),
        one_week_percent=Decimal("-7.45"),
        rank=1,
    )
    result = analyze_symbol(
        {
            "ticker": "FIZZ",
            "signal": "REVIEW",
            "report_path": "/tmp/report.md",
            "final_decision": "**Rating**: Hold\n\n**Price Target**: 34.0",
            "structured_decision": {
                "rating": "Hold",
                "entry": "31.59",
                "stop": "28.0",
                "target": "34.0",
                "horizon": "6-12 months",
                "why": "Wait for rebound above the 10-day EMA.",
            },
        },
        screened,
    )
    assert result.signal == "Hold"
    assert result.price_target == "34.0"
    assert result.stop == "28.0"
    assert result.entry_hint == "31.59"
    assert result.error is None
    assert result.screened is screened
    assert result.report_path == "/tmp/report.md"


def test_analyze_symbol_keeps_overweight_without_target() -> None:
    result = analyze_symbol(
        {
            "ticker": "AMGN",
            "structured_decision": {
                "rating": "Overweight",
                "entry": "381.5",
                "stop": "373.5",
                "target": None,
                "horizon": "6-12 months",
                "why": "Entry and stop stated; no price target section.",
            },
        },
        None,
    )
    assert result.signal == "Overweight"
    assert result.entry_hint == "381.5"
    assert result.stop == "373.5"
    assert result.price_target is None
    assert result.error is None
    assert result.advisory_plan_complete is False
    assert result.advisory_plan_error == "incomplete advisory price plan"


def test_is_bullish_signal() -> None:
    assert is_bullish_signal("Buy")
    assert is_bullish_signal("Overweight")
    assert not is_bullish_signal("Hold")
    assert not is_bullish_signal(None)


def test_partial_nonbullish_plan_keeps_rating_but_is_explicitly_incomplete():
    result = analyze_symbol(
        {
            "ticker": "PAGS",
            "structured_decision": {
                "rating": "Underweight",
                "entry": 8.56,
                "stop": None,
                "target": None,
                "horizon": "3 months",
                "why": "Avoid new exposure.",
            },
        },
        None,
    )
    assert result.signal == "Underweight"
    assert result.error is None
    assert result.entry_hint == "8.56"
    assert result.stop is None
    assert result.advisory_plan_complete is False
    assert result.advisory_plan_error == "incomplete advisory price plan"


def test_valid_hold_without_trade_plan_is_not_unavailable() -> None:
    result = analyze_symbol(
        {
            "ticker": "NTES",
            "structured_decision": {
                "rating": "Hold",
                "entry": None,
                "stop": None,
                "target": None,
                "horizon": "3-6 months",
                "why": "Wait for regulatory clarity.",
            },
        },
        None,
    )
    assert result.signal == "Hold"
    assert result.error is None
    assert result.entry_hint is None
    assert result.stop is None
    assert result.price_target is None
    assert not is_bullish_signal(result.signal)


def test_qualifies_on_upside_uses_target_against_live_price() -> None:
    assert qualifies_on_upside("Hold", "28.0", Decimal("23.94"))
    assert not qualifies_on_upside("Hold", "25.0", Decimal("24.50"))
    assert not qualifies_on_upside("Underweight", "40.0", Decimal("20.00"))
    assert not qualifies_on_upside("Hold", None, Decimal("20.00"))
    assert not qualifies_on_upside("Hold", "28.0", None)


def test_analyze_symbol_fails_closed_on_markdown_without_json() -> None:
    result = analyze_symbol(
        {
            "ticker": "FIZZ",
            "signal": "Buy",
            "final_decision": "**Rating**: Buy\n\n**Price Target**: 40.0",
        },
        None,
    )
    assert result.signal == "UNAVAILABLE"
    assert result.price_target is None
    assert result.error is not None
    assert "JSON" in result.error or "structured" in result.error


def test_analyze_symbol_fails_closed_on_review() -> None:
    result = analyze_symbol(
        {
            "ticker": "FIZZ",
            "structured_decision": {
                "rating": "REVIEW",
                "entry": 31.59,
                "stop": 28.0,
                "target": 34.0,
                "horizon": "6-12 months",
                "why": "No quote in this debate.",
            },
        },
        None,
    )
    assert result.signal == "UNAVAILABLE"
    assert result.error is not None
    assert "REVIEW" in result.error


def test_format_price() -> None:
    assert format_price(Decimal("29.83")) == "$29.83"
    assert format_price(None) == "-"


@patch("nomy_trader.analysis.pipeline.run_tradingagents_subprocess")
def test_analyze_symbols_records_errors(mock_run) -> None:
    from nomy_trader.analysis.pipeline import analyze_symbols

    mock_run.side_effect = RuntimeError("timeout")
    results = analyze_symbols(("FIZZ",))
    assert len(results) == 1
    assert results[0].error == "timeout"


def test_force_refresh_bypasses_warm_result_and_requests_fresh_provider_data(
    tmp_path: Path,
) -> None:
    from nomy_trader.analysis.cache import TradingAgentsCacheEntry, save_cache_entry
    from nomy_trader.analysis.pipeline import _run_symbol_analysis

    now = datetime(2026, 10, 15, tzinfo=UTC)
    save_cache_entry(
        TradingAgentsCacheEntry(
            symbol="CRDO",
            profile_key="test",
            analyzed_at=now,
            runner_payload={"ticker": "CRDO", "signal": "Buy"},
        ),
        project_root=tmp_path,
    )
    overrides = {"TRADINGAGENTS_QUICK_THINK_LLM": "test-model"}
    with patch("nomy_trader.analysis.pipeline.run_tradingagents_subprocess") as run:
        run.return_value = {"ticker": "CRDO", "signal": "Hold"}
        result = _run_symbol_analysis(
            "CRDO",
            None,
            env_overrides=overrides,
            profile_key="test",
            project_root=tmp_path,
            timeout_seconds=60,
            clock=now,
            force_refresh=True,
        )
    assert result.source == "live"
    assert result.signal == "UNAVAILABLE"  # Fresh unstructured output fails closed.
    assert run.call_args.kwargs["env_overrides"]["NOMY_FORCE_FRESH_DATA"] == "1"
    assert "NOMY_FORCE_FRESH_DATA" not in overrides
