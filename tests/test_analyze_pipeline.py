from decimal import Decimal
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


def test_is_bullish_signal() -> None:
    assert is_bullish_signal("Buy")
    assert is_bullish_signal("Overweight")
    assert not is_bullish_signal("Hold")
    assert not is_bullish_signal(None)


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
