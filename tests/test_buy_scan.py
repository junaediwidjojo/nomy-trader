from datetime import UTC, datetime

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
