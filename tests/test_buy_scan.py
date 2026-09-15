from datetime import UTC, datetime
from decimal import Decimal

from nomy_trader.analysis.buy_scan import summarize_buy_candidates
from nomy_trader.analysis.pipeline import SymbolAnalysis


def test_summarize_buy_candidates_classifies_confirmation() -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    results = (
        SymbolAnalysis(
            symbol="AAA",
            signal="Buy",
            confirmatory=SymbolAnalysis(symbol="AAA", signal="Hold"),
        ),
        SymbolAnalysis(
            symbol="BBB",
            signal="Overweight",
            confirmatory=SymbolAnalysis(symbol="BBB", signal="Buy"),
        ),
        SymbolAnalysis(symbol="CCC", signal="Hold"),
    )
    summary = summarize_buy_candidates(
        results,
        observed_at=now,
        catalogue_revision="rev",
        candidates_screened=10,
    )
    assert summary.primary_bullish == ("AAA", "BBB")
    assert summary.confirmed_bullish == ("BBB",)
    assert summary.disputed_bullish == ("AAA",)


def test_hold_with_material_target_upside_becomes_a_candidate() -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    results = (
        SymbolAnalysis(
            symbol="UPS",
            signal="Hold",
            price_target="28.0",
            reference_price=Decimal("23.94"),
            target_upside=Decimal("0.1696"),
            confirmatory=SymbolAnalysis(symbol="UPS", signal="Buy"),
        ),
        SymbolAnalysis(
            symbol="FLAT",
            signal="Hold",
            price_target="25.0",
            reference_price=Decimal("24.50"),
        ),
        SymbolAnalysis(
            symbol="BEAR",
            signal="Underweight",
            price_target="40.0",
            reference_price=Decimal("20.00"),
        ),
    )
    summary = summarize_buy_candidates(
        results,
        observed_at=now,
        catalogue_revision="rev",
        candidates_screened=10,
    )
    assert summary.primary_bullish == ()
    assert summary.upside_candidates == ("UPS",)
    assert summary.confirmed_bullish == ("UPS",)
    assert summary.rows[0].trigger == "upside_target"
