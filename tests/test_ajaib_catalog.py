from pathlib import Path

import pytest

from nomy_trader.market.ajaib_catalog import load_ajaib_catalog


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
