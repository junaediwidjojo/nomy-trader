"""Immutable source/plan journal and transactional notification outbox."""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("payload", sa.Text, nullable=False),
    )
    for name in ("evidence", "decisions", "plans"):
        op.create_table(
            name,
            sa.Column("id", sa.Text, primary_key=True),
            sa.Column("event_id", sa.Text, sa.ForeignKey("events.id"), nullable=False),
            sa.Column("payload", sa.Text, nullable=False),
        )
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("idempotency_key", sa.Text, nullable=False, unique=True),
        sa.Column("plan_id", sa.Text, sa.ForeignKey("plans.id"), nullable=False),
        sa.Column(
            "decision_id", sa.Text, sa.ForeignKey("decisions.id"), nullable=False
        ),
        sa.Column("payload", sa.Text, nullable=False),
    )
    op.create_table(
        "recommendation_evidence",
        sa.Column(
            "recommendation_id",
            sa.Text,
            sa.ForeignKey("recommendations.id"),
            primary_key=True,
        ),
        sa.Column(
            "evidence_id", sa.Text, sa.ForeignKey("evidence.id"), primary_key=True
        ),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Text,
            sa.ForeignKey("recommendations.id"),
            nullable=False,
        ),
        sa.Column("destination_alias", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.UniqueConstraint("recommendation_id", "destination_alias"),
        sa.CheckConstraint("status IN ('PENDING','SENDING','SENT','FAILED','UNKNOWN')"),
    )
    op.create_table(
        "notification_attempts",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("outbox_id", sa.Text, sa.ForeignKey("outbox.id"), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
    )
    for table in (
        "events",
        "evidence",
        "decisions",
        "plans",
        "recommendations",
        "recommendation_evidence",
        "notification_attempts",
    ):
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER immutable_{table}_{action.lower()} "
                f"BEFORE {action} ON {table} BEGIN "
                "SELECT RAISE(ABORT, 'immutable journal record'); END"
            )


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup")
