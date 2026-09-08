"""Atomic immutable journal writes. No notification is sent from this module."""

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Connection, Engine

from nomy_trader.domain.models import (
    Contract,
    Decision,
    Event,
    Evidence,
    PipelineHealth,
    Recommendation,
    RecommendationPolicy,
)
from nomy_trader.domain.validation import validate_recommendation

from . import schema


def _store(
    conn: Connection, table: sa.Table, identity: str, record: Contract, **links: str
) -> None:
    payload = record.model_dump_json()
    existing = conn.execute(
        sa.select(table.c.payload).where(table.c.id == identity)
    ).scalar_one_or_none()
    if existing is not None:
        if existing != payload:
            raise ValueError("immutable record identity conflicts with stored content")
        return
    conn.execute(table.insert().values(id=identity, payload=payload, **links))


def record_recommendation(
    engine: Engine,
    *,
    recommendation: Recommendation,
    decision: Decision,
    event: Event,
    evidence: tuple[Evidence, ...],
    policy: RecommendationPolicy,
    health: PipelineHealth,
    now: datetime,
    destination_alias: str,
) -> str:
    """Return stable local outbox ID for the same recommendation/destination.

    Destination is an application alias, not a token or actual Telegram chat ID.
    Conflicting reused IDs fail rather than overwriting historical facts.
    """
    if not destination_alias.strip():
        raise ValueError("destination alias required")
    validate_recommendation(
        recommendation, decision, event, evidence, policy, health, now
    )
    plan = recommendation.plan
    with engine.begin() as conn:
        _store(conn, schema.events, event.id, event)
        for item in evidence:
            _store(conn, schema.evidence, item.id, item, event_id=item.event_id)
        _store(conn, schema.decisions, decision.id, decision, event_id=event.id)
        _store(conn, schema.plans, plan.id, plan, event_id=event.id)
        _store(
            conn,
            schema.recommendations,
            recommendation.id,
            recommendation,
            idempotency_key=recommendation.idempotency_key,
            plan_id=plan.id,
            decision_id=decision.id,
        )
        for ref in plan.evidence_ids:
            present = conn.execute(
                sa.select(schema.recommendation_evidence).where(
                    schema.recommendation_evidence.c.recommendation_id
                    == recommendation.id,
                    schema.recommendation_evidence.c.evidence_id == ref,
                )
            ).first()
            if present is None:
                conn.execute(
                    schema.recommendation_evidence.insert().values(
                        recommendation_id=recommendation.id,
                        evidence_id=ref,
                    )
                )
        existing = conn.execute(
            sa.select(schema.outbox.c.id).where(
                schema.outbox.c.recommendation_id == recommendation.id,
                schema.outbox.c.destination_alias == destination_alias,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return str(existing)
        outbox_id = str(uuid4())
        conn.execute(
            schema.outbox.insert().values(
                id=outbox_id,
                recommendation_id=recommendation.id,
                destination_alias=destination_alias,
                status="PENDING",
            )
        )
        return outbox_id


def read_recommendation(engine: Engine, identity: str) -> Recommendation:
    with engine.connect() as conn:
        payload = conn.execute(
            sa.select(schema.recommendations.c.payload).where(
                schema.recommendations.c.id == identity,
            )
        ).scalar_one()
    return Recommendation.model_validate_json(payload)
