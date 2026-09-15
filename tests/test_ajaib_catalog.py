from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from nomy_trader.market.ajaib_catalog import (
    import_user_catalog,
    load_ajaib_catalog,
    load_latest_imported_catalog,
)
from nomy_trader.market.ajaib_hints import (
    DEFAULT_PRIORITY_POLICY,
    AjaibReversalHint,
    rank_reversal_hints,
    run_reversal_hint_scan,
)
from nomy_trader.storage.database import open_database, upgrade


def test_user_supplied_snapshot_has_expected_catalogue_screen():
    snapshot = load_ajaib_catalog(Path("config/ajaib_catalog_snapshot.json"))
    assert snapshot.catalog_entry_count == 739
    assert len(snapshot.symbols) == 137
    assert snapshot.accepts("APTV")
    assert not snapshot.accepts("FCUV")


@pytest.mark.parametrize(
    "content",
    ["{}", '{"revision":"x","symbols":["A","A"]}'],
)
def test_invalid_or_ambiguous_snapshot_fails_closed(tmp_path, content):
    path = tmp_path / "catalog.json"
    path.write_text(content)
    with pytest.raises(ValueError, match="Ajaib catalogue snapshot is invalid"):
        load_ajaib_catalog(path)


def test_import_persists_full_response_and_derives_working_universe(tmp_path):
    source = tmp_path / "ajaib.json"
    source.write_text(
        '{"err_message":"APPROVED/OK","result":{"count":2,"results":['
        '{"code":"GOOD","name":"Good","price":5.01,"market_cap":100000001},'
        '{"code":"SMALL","name":"Small","price":20,"market_cap":100000000}]}}'
    )
    engine = open_database(tmp_path / "catalog.sqlite")
    upgrade(engine)
    snapshot = import_user_catalog(engine, source, datetime(2026, 9, 9, tzinfo=UTC))
    assert snapshot.symbols == ("GOOD",)
    assert load_latest_imported_catalog(engine) == snapshot
    engine.dispose()


def test_reversal_hints_require_all_approved_boundaries_and_log_rejections(tmp_path):
    source = tmp_path / "ajaib.json"
    source.write_text(
        '{"err_message":"APPROVED/OK","result":{"count":3,"results":['
        '{"code":"HINT","name":"Hint","price":11,"market_cap":250000001,'
        '"price_1_day":{"pct_change":-1.5},'
        '"price_1_week":{"pct_change":-4},'
        '"price_1_month":{"pct_change":-100}},'
        '{"code":"SMALL","name":"Small","price":11,"market_cap":250000000,'
        '"price_1_day":{"pct_change":-1.49},'
        '"price_1_week":{"pct_change":-4},'
        '"price_1_month":{"pct_change":-10}},'
        '{"code":"FLAT","name":"Flat","price":11,"market_cap":250000001,'
        '"price_1_day":{"pct_change":-6},'
        '"price_1_week":{"pct_change":-3.99},'
        '"price_1_month":{"pct_change":-9.99}}]}}'
    )
    engine = open_database(tmp_path / "catalog.sqlite")
    upgrade(engine)
    now = datetime(2026, 9, 9, tzinfo=UTC)
    import_user_catalog(engine, source, now)

    scan = run_reversal_hint_scan(engine, now)

    assert [hint.symbol for hint in scan.candidates] == ["HINT"]
    assert scan.rejections[0].symbol == "SMALL"
    assert "market_cap_not_above_250m" in scan.rejections[0].reasons
    assert scan.rejections[1].symbol == "FLAT"
    assert "no_week_or_month_drawdown" in scan.rejections[1].reasons


def test_month_drawdown_alone_qualifies_a_stabilized_selloff(tmp_path):
    source = tmp_path / "ajaib.json"
    source.write_text(
        '{"err_message":"APPROVED/OK","result":{"count":1,"results":['
        '{"code":"CALM","name":"Calm","price":11,"market_cap":250000001,'
        '"price_1_day":{"pct_change":0.4},'
        '"price_1_week":{"pct_change":-1},'
        '"price_1_month":{"pct_change":-18}}]}}'
    )
    engine = open_database(tmp_path / "catalog.sqlite")
    upgrade(engine)
    now = datetime(2026, 9, 9, tzinfo=UTC)
    import_user_catalog(engine, source, now)

    scan = run_reversal_hint_scan(engine, now)

    assert [hint.symbol for hint in scan.candidates] == ["CALM"]
    engine.dispose()
    engine.dispose()


def test_priority_rank_is_explainable_and_ties_break_by_symbol():
    def hint(symbol: str, day: str, month: str | None) -> AjaibReversalHint:
        return AjaibReversalHint(
            symbol=symbol,
            issuer_name=f"{symbol} Inc.",
            price=Decimal("10"),
            market_cap=250_000_001,
            one_day_percent=Decimal(day),
            one_week_percent=Decimal("-4"),
            one_month_percent=Decimal(month) if month is not None else None,
        )

    ranked = rank_reversal_hints(
        (
            hint("PROLONGED", "-8", "-20"),
            hint("RECENT", "-8", "2"),
            hint("ALPHA", "-5", None),
            hint("BETA", "-5", None),
        ),
        DEFAULT_PRIORITY_POLICY,
    )

    assert [item.hint.symbol for item in ranked] == [
        "RECENT",
        "PROLONGED",
        "ALPHA",
        "BETA",
    ]
    assert ranked[0].breakdown.one_day_severity == Decimal("2.0")
    assert ranked[0].breakdown.one_week_severity == Decimal("4.0")
    assert ranked[0].breakdown.one_month_reversal_context == Decimal("1.5")
    assert ranked[1].breakdown.one_month_reversal_context == Decimal("0.00")
    assert ranked[2].breakdown.total == Decimal("5.25")


def test_stabilized_weekly_drawdown_outranks_same_day_crash():
    def hint(symbol: str, day: str, week: str) -> AjaibReversalHint:
        return AjaibReversalHint(
            symbol=symbol,
            issuer_name=f"{symbol} Inc.",
            price=Decimal("10"),
            market_cap=250_000_001,
            one_day_percent=Decimal(day),
            one_week_percent=Decimal(week),
            one_month_percent=Decimal("-12"),
        )

    ranked = rank_reversal_hints(
        (
            hint("CRASH", "-6", "-7"),
            hint("AMGNLIKE", "0.4", "-13"),
        ),
        DEFAULT_PRIORITY_POLICY,
    )
    assert [item.hint.symbol for item in ranked] == ["AMGNLIKE", "CRASH"]


def test_ranked_scan_keeps_base_candidates_and_persists_policy(tmp_path):
    source = tmp_path / "ajaib.json"
    source.write_text(
        '{"err_message":"APPROVED/OK","result":{"count":2,"results":['
        '{"code":"LOW","name":"Low","price":11,"market_cap":250000001,'
        '"price_1_day":{"pct_change":-8},"price_1_week":{"pct_change":-4},'
        '"price_1_month":{"pct_change":-20}},'
        '{"code":"RECENT","name":"Recent","price":11,"market_cap":250000001,'
        '"price_1_day":{"pct_change":-8},"price_1_week":{"pct_change":-4},'
        '"price_1_month":{"pct_change":-8}}]}}'
    )
    engine = open_database(tmp_path / "catalog.sqlite")
    now = datetime(2026, 9, 9, tzinfo=UTC)
    upgrade(engine)
    import_user_catalog(engine, source, now)

    scan = run_reversal_hint_scan(engine, now)

    assert [hint.symbol for hint in scan.candidates] == ["LOW", "RECENT"]
    assert scan.ranked_candidates[0].hint.symbol == "RECENT"
    assert scan.priority_policy == DEFAULT_PRIORITY_POLICY
    engine.dispose()
