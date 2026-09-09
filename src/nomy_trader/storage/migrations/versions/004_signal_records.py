"""Immutable completed signal workflow journal."""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_records",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("event_id", sa.Text, nullable=False),
        sa.Column("recorded_at", sa.Text, nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
    )
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER immutable_signal_records_{action.lower()} "
            f"BEFORE {action} ON signal_records BEGIN "
            "SELECT RAISE(ABORT, 'immutable signal record'); END"
        )


def downgrade() -> None:
    raise RuntimeError("Restore a verified backup instead of deleting signal history")
