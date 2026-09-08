import pytest
import sqlalchemy as sa

from nomy_trader.storage import schema
from nomy_trader.storage.database import open_database, upgrade


def test_migration_idempotent_and_foreign_keys(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    upgrade(engine)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert set(schema.metadata.tables).issubset(sa.inspect(conn).get_table_names())
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(
            schema.plans.insert().values(id="p", event_id="missing", payload="{}")
        )
    engine.dispose()


def test_journal_cannot_overwrite_or_delete(tmp_path):
    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    with engine.begin() as conn:
        conn.execute(schema.events.insert().values(id="event-1", payload="original"))
    for command in (
        schema.events.update().values(payload="changed"),
        schema.events.delete(),
    ):
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
            conn.execute(command)
    with engine.connect() as conn:
        assert conn.execute(sa.select(schema.events.c.payload)).scalar() == "original"
    engine.dispose()
