"""Connection setup and programmatic Alembic migration entry point."""

from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, event


def open_database(path: Path) -> Engine:
    engine = sa.create_engine(sa.URL.create("sqlite", database=str(path)))

    @event.listens_for(engine, "connect")
    def configure(connection: Any, record: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")

    return engine


def upgrade(engine: Engine, revision: str = "head") -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
