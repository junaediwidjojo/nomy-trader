from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from nomy_trader.market.ajaib_hints import (
    DEFAULT_PRIORITY_POLICY,
    AjaibReversalHint,
    rank_reversal_hints,
)
from nomy_trader.market.fmp_prescreen import (
    evaluate_fmp_profile,
    prescreen_ranked_hints,
)
from nomy_trader.providers.fmp import CompanyProfile, FmpClient
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.quota import QuotaWindow

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def _hint(symbol: str = "ABC", price: str = "90") -> AjaibReversalHint:
    return AjaibReversalHint(
        symbol=symbol,
        issuer_name="Example",
        price=Decimal(price),
        market_cap=250_000_001,
        one_day_percent=Decimal("-3"),
        one_week_percent=Decimal("-6"),
        one_month_percent=Decimal("-10"),
    )


def _profile(
    symbol: str = "ABC",
    *,
    price: str = "90",
    change: str = "-3.2",
    volume: str = "1000000",
    is_etf: bool = False,
) -> CompanyProfile:
    return CompanyProfile(
        symbol=symbol,
        price=Decimal(price),
        marketCap=Decimal("400000000"),
        volume=Decimal(volume),
        averageVolume=Decimal(volume),
        changePercentage=Decimal(change),
        isEtf=is_etf,
        isFund=False,
        isActivelyTrading=True,
    )


def test_evaluate_accepts_liquid_live_decline() -> None:
    row = evaluate_fmp_profile(_hint(), _profile())
    assert row.passed


def test_evaluate_rejects_etf_disagreement_and_rebounded_name() -> None:
    etf = evaluate_fmp_profile(_hint(), _profile(is_etf=True))
    assert "fmp_is_etf" in etf.reasons
    mismatch = evaluate_fmp_profile(_hint(price="10.50"), _profile())
    assert "fmp_ajaib_price_disagreement" in mismatch.reasons
    rebounded = evaluate_fmp_profile(_hint(), _profile(change="4.5"))
    assert "fmp_already_rebounded_above_3_percent" in rebounded.reasons


def test_evaluate_keeps_a_selloff_that_stopped_falling() -> None:
    steady = evaluate_fmp_profile(_hint(), _profile(change="-0.2"))
    assert steady.passed
    drifting_up = evaluate_fmp_profile(_hint(), _profile(change="1.1"))
    assert drifting_up.passed


def test_prescreen_is_quota_accounted(tmp_path) -> None:
    def send(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params["symbol"]
        change = "-3.2" if symbol == "GOOD" else "7.5"
        profile = _profile(symbol, price="90", change=change)
        return httpx.Response(200, json=[profile.model_dump(mode="json")])

    client = FmpClient("test-key", httpx.Client(transport=httpx.MockTransport(send)))
    engine = open_database(tmp_path / "prescreen.sqlite")
    upgrade(engine)
    ranked = rank_reversal_hints(
        (_hint("SKIP", "90"), _hint("GOOD", "90")),
        DEFAULT_PRIORITY_POLICY,
    )
    window = QuotaWindow(
        id="fmp-prescreen-test",
        budget_name="fmp-prescreen-test",
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(days=1),
        call_limit=10,
    )
    result = prescreen_ranked_hints(
        engine, client, ranked, now=NOW, quota_window=window
    )
    assert [item.hint.symbol for item in result.passed] == ["GOOD"]
    skipped = next(row for row in result.rows if row.symbol == "SKIP")
    assert not skipped.passed
    assert all(row.source == "live" for row in result.rows)
    engine.dispose()


def test_recent_observations_are_reused_without_new_calls(tmp_path) -> None:
    calls: list[str] = []

    def send(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params["symbol"]
        calls.append(symbol)
        profile = _profile(symbol, price="90", change="-3.2")
        return httpx.Response(200, json=[profile.model_dump(mode="json")])

    client = FmpClient("test-key", httpx.Client(transport=httpx.MockTransport(send)))
    engine = open_database(tmp_path / "prescreen.sqlite")
    upgrade(engine)
    ranked = rank_reversal_hints((_hint("GOOD", "90"),), DEFAULT_PRIORITY_POLICY)
    window = QuotaWindow(
        id="fmp-prescreen-reuse",
        budget_name="fmp-prescreen-reuse",
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(days=1),
        call_limit=10,
    )

    first = prescreen_ranked_hints(engine, client, ranked, now=NOW, quota_window=window)
    second = prescreen_ranked_hints(
        engine, client, ranked, now=NOW, quota_window=window
    )

    assert calls == ["GOOD"]
    assert first.rows[0].source == "live"
    assert second.rows[0].source == "cache"
    assert [item.hint.symbol for item in second.passed] == ["GOOD"]
    engine.dispose()
