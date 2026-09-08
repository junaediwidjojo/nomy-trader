"""Migrations run through storage.database.upgrade with an explicit connection."""

from alembic import context

from nomy_trader.storage.schema import metadata

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=metadata)
with context.begin_transaction():
    context.run_migrations()
