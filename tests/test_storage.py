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


def test_atomic_write_repeat_and_restart(tmp_path):
    from nomy_trader.fixtures import context
    from nomy_trader.storage.journal import read_recommendation, record_recommendation

    path = tmp_path / "journal.sqlite"
    engine = open_database(path)
    upgrade(engine)
    args = context()
    identity = record_recommendation(engine, **args, destination_alias="private")
    assert (
        record_recommendation(engine, **args, destination_alias="private") == identity
    )
    engine.dispose()
    restarted = open_database(path)
    assert read_recommendation(restarted, "rec-1") == args["recommendation"]
    assert (
        record_recommendation(restarted, **args, destination_alias="private")
        == identity
    )
    with restarted.connect() as conn:
        assert (
            conn.execute(sa.select(sa.func.count()).select_from(schema.outbox)).scalar()
            == 1
        )
        assert conn.execute(sa.select(schema.outbox.c.status)).scalar() == "PENDING"
    restarted.dispose()


def test_outbox_failure_rolls_back_entire_recommendation(tmp_path):
    from nomy_trader.fixtures import context
    from nomy_trader.storage.journal import record_recommendation

    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox "
            "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )
    with pytest.raises(sa.exc.IntegrityError):
        record_recommendation(engine, **context(), destination_alias="private")
    with engine.connect() as conn:
        for table in (
            schema.events,
            schema.evidence,
            schema.plans,
            schema.recommendations,
            schema.outbox,
        ):
            assert (
                conn.execute(sa.select(sa.func.count()).select_from(table)).scalar()
                == 0
            )
    engine.dispose()


def test_conflicting_recommendation_cannot_replace_history(tmp_path):
    from nomy_trader.fixtures import context
    from nomy_trader.storage.journal import read_recommendation, record_recommendation

    engine = open_database(tmp_path / "journal.sqlite")
    upgrade(engine)
    args = context()
    record_recommendation(engine, **args, destination_alias="private")
    original = args["recommendation"]
    args["recommendation"] = type(original).model_validate(
        {
            **original.model_dump(),
            "idempotency_key": "changed",
        }
    )
    with pytest.raises(ValueError):
        record_recommendation(engine, **args, destination_alias="private")
    assert read_recommendation(engine, "rec-1") == original
    engine.dispose()
