from datetime import UTC, datetime
from pathlib import Path

import pytest

from nomy_trader.market.ajaib_catalog import (
    import_user_catalog,
    load_ajaib_catalog,
    load_latest_imported_catalog,
)
from nomy_trader.market.ajaib_hints import run_reversal_hint_scan
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
        '"price_1_day":{"pct_change":-2},'
        '"price_1_week":{"pct_change":-4},'
        '"price_1_month":{"pct_change":0.01}},'
        '{"code":"DAY","name":"Day","price":6,"market_cap":100000001,'
        '"price_1_day":{"pct_change":-1.99},'
        '"price_1_week":{"pct_change":-4},'
        '"price_1_month":{"pct_change":1}},'
        '{"code":"MONTH","name":"Month","price":6,"market_cap":100000001,'
        '"price_1_day":{"pct_change":-6},'
        '"price_1_week":{"pct_change":-4},'
        '"price_1_month":{"pct_change":0}}]}}'
    )
    engine = open_database(tmp_path / "catalog.sqlite")
    upgrade(engine)
    now = datetime(2026, 9, 9, tzinfo=UTC)
    import_user_catalog(engine, source, now)

    scan = run_reversal_hint_scan(engine, now)

    assert [hint.symbol for hint in scan.candidates] == ["HINT"]
    assert scan.rejections[0].symbol == "DAY"
    assert "one_day_decline_not_at_least_2_percent" in scan.rejections[0].reasons
    assert scan.rejections[1].symbol == "MONTH"
    assert "one_month_change_not_positive" in scan.rejections[1].reasons
    engine.dispose()
