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
        '{"code":"HINT","name":"Hint","price":6,"market_cap":100000001,'
        '"price_1_day":{"pct_change":-1},'
        '"price_1_week":{"pct_change":-3},'
        '"price_1_month":{"pct_change":-100}},'
        '{"code":"DAY","name":"Day","price":6,"market_cap":100000001,'
        '"price_1_day":{"pct_change":-0.99},'
        '"price_1_week":{"pct_change":-3},'
        '"price_1_month":{"pct_change":1}},'
        '{"code":"WEEK","name":"Week","price":6,"market_cap":100000001,'
        '"price_1_day":{"pct_change":-6},'
        '"price_1_week":{"pct_change":-2.99},'
        '"price_1_month":{"pct_change":-4}}]}}'
    )
    engine = open_database(tmp_path / "catalog.sqlite")
    upgrade(engine)
    now = datetime(2026, 9, 9, tzinfo=UTC)
    import_user_catalog(engine, source, now)

    scan = run_reversal_hint_scan(engine, now)

    assert [hint.symbol for hint in scan.candidates] == ["HINT"]
    assert scan.rejections[0].symbol == "DAY"
    assert "one_day_decline_not_at_least_1_percent" in scan.rejections[0].reasons
    assert scan.rejections[1].symbol == "WEEK"
    assert "one_week_decline_not_at_least_3_percent" in scan.rejections[1].reasons
    engine.dispose()


def test_priority_rank_is_explainable_and_ties_break_by_symbol():
    def hint(symbol: str, day: str, month: str | None) -> AjaibReversalHint:
        return AjaibReversalHint(
            symbol=symbol,
            issuer_name=f"{symbol} Inc.",
            price=Decimal("10"),
            market_cap=100_000_001,
            one_day_percent=Decimal(day),
            one_week_percent=Decimal("-3"),
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
    assert ranked[0].breakdown.one_day_severity == Decimal("8.0")
    assert ranked[0].breakdown.one_month_reversal_context == Decimal("2.000")
    assert ranked[1].breakdown.one_month_reversal_context == Decimal("0.00")
    assert ranked[2].breakdown.total == Decimal("5.0")


def test_ranked_scan_keeps_base_candidates_and_persists_policy(tmp_path):
    source = tmp_path / "ajaib.json"
    source.write_text(
        '{"err_message":"APPROVED/OK","result":{"count":2,"results":['
        '{"code":"LOW","name":"Low","price":6,"market_cap":100000001,'
        '"price_1_day":{"pct_change":-9},"price_1_week":{"pct_change":-3},'
        '"price_1_month":{"pct_change":-20}},'
        '{"code":"RECENT","name":"Recent","price":6,"market_cap":100000001,'
        '"price_1_day":{"pct_change":-8},"price_1_week":{"pct_change":-3},'
        '"price_1_month":{"pct_change":10}}]}}'
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
