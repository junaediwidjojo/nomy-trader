"""Persistent request reservations, market snapshots and scan history."""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quota_windows",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("budget_name", sa.Text, nullable=False),
        sa.Column("starts_at", sa.Text, nullable=False),
        sa.Column("ends_at", sa.Text, nullable=False),
        sa.Column("call_limit", sa.Integer, nullable=False),
        sa.CheckConstraint("call_limit > 0"),
    )
    op.create_table(
        "quota_reservations",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "window_id", sa.Text, sa.ForeignKey("quota_windows.id"), nullable=False
        ),
        sa.Column("reserved_at", sa.Text, nullable=False),
        sa.Column("calls", sa.Integer, nullable=False),
        sa.CheckConstraint("calls > 0"),
    )
    op.create_table(
        "market_cache",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("cache_key", sa.Text, nullable=False),
        sa.Column("source_as_of", sa.Text, nullable=False),
        sa.Column("retrieved_at", sa.Text, nullable=False),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
    )
    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("started_at", sa.Text, nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
    )
    for table in ("quota_windows", "quota_reservations", "market_cache", "scan_runs"):
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER immutable_{table}_{action.lower()} "
                f"BEFORE {action} ON {table} BEGIN "
                "SELECT RAISE(ABORT, 'immutable journal record'); END"
            )


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup")
