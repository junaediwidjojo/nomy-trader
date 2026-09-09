"""Separate rolling provider rate accounting."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_requests",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("reserved_at", sa.Float, nullable=False),
    )
    op.create_index(
        "ix_provider_requests_time", "provider_requests", ["provider", "reserved_at"]
    )
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER immutable_requests_{action.lower()} "
            f"BEFORE {action} ON provider_requests BEGIN "
            "SELECT RAISE(ABORT, 'immutable request reservation'); END"
        )


def downgrade() -> None:
    raise RuntimeError("Restore a verified backup instead of deleting quota history")
