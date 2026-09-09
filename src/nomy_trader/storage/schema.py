"""SQLAlchemy table contracts; migrations own database creation."""

import sqlalchemy as sa

metadata = sa.MetaData()
provider_requests = sa.Table(
    "provider_requests",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("provider", sa.Text, nullable=False),
    sa.Column("reserved_at", sa.Float, nullable=False),
)
events = sa.Table(
    "events",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("payload", sa.Text, nullable=False),
)
evidence = sa.Table(
    "evidence",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("event_id", sa.Text, sa.ForeignKey("events.id"), nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)
decisions = sa.Table(
    "decisions",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("event_id", sa.Text, sa.ForeignKey("events.id"), nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)
plans = sa.Table(
    "plans",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("event_id", sa.Text, sa.ForeignKey("events.id"), nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)
recommendations = sa.Table(
    "recommendations",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("idempotency_key", sa.Text, nullable=False, unique=True),
    sa.Column("plan_id", sa.Text, sa.ForeignKey("plans.id"), nullable=False),
    sa.Column("decision_id", sa.Text, sa.ForeignKey("decisions.id"), nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)
recommendation_evidence = sa.Table(
    "recommendation_evidence",
    metadata,
    sa.Column(
        "recommendation_id",
        sa.Text,
        sa.ForeignKey("recommendations.id"),
        primary_key=True,
    ),
    sa.Column("evidence_id", sa.Text, sa.ForeignKey("evidence.id"), primary_key=True),
)
outbox = sa.Table(
    "outbox",
    metadata,
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
attempts = sa.Table(
    "notification_attempts",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("outbox_id", sa.Text, sa.ForeignKey("outbox.id"), nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)

quota_windows = sa.Table(
    "quota_windows",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("budget_name", sa.Text, nullable=False),
    sa.Column("starts_at", sa.Text, nullable=False),
    sa.Column("ends_at", sa.Text, nullable=False),
    sa.Column("call_limit", sa.Integer, nullable=False),
    sa.CheckConstraint("call_limit > 0"),
)
quota_reservations = sa.Table(
    "quota_reservations",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("window_id", sa.Text, sa.ForeignKey("quota_windows.id"), nullable=False),
    sa.Column("reserved_at", sa.Text, nullable=False),
    sa.Column("calls", sa.Integer, nullable=False),
    sa.CheckConstraint("calls > 0"),
)
cache = sa.Table(
    "market_cache",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("cache_key", sa.Text, nullable=False),
    sa.Column("source_as_of", sa.Text, nullable=False),
    sa.Column("retrieved_at", sa.Text, nullable=False),
    sa.Column("expires_at", sa.Text, nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)
scan_runs = sa.Table(
    "scan_runs",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("started_at", sa.Text, nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)
