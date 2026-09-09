"""Immutable persistence for reproducible completed signal workflows."""

import sqlalchemy as sa
from sqlalchemy import Engine

from nomy_trader.signals import CompletedSignal

from . import schema


def record_completed_signal(engine: Engine, signal: CompletedSignal) -> None:
    """Store a completed signal once; conflicting reused identities fail closed."""
    payload = signal.model_dump_json()
    with engine.begin() as connection:
        existing = connection.execute(
            sa.select(schema.signal_records.c.payload).where(
                schema.signal_records.c.id == signal.id
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing != payload:
                raise ValueError(
                    "immutable signal identity conflicts with stored content"
                )
            return
        connection.execute(
            schema.signal_records.insert().values(
                id=signal.id,
                symbol=signal.fixture.evidence_packet.symbol,
                event_id=signal.fixture.evidence_packet.event_id,
                recorded_at=signal.recorded_at.isoformat(),
                payload=payload,
            )
        )


def read_completed_signal(engine: Engine, identity: str) -> CompletedSignal:
    """Read and revalidate a single immutable completed signal."""
    with engine.connect() as connection:
        payload = connection.execute(
            sa.select(schema.signal_records.c.payload).where(
                schema.signal_records.c.id == identity
            )
        ).scalar_one()
    return CompletedSignal.model_validate_json(payload)
