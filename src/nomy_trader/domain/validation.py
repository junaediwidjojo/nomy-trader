"""Pure aggregate validation. No state mutations or provider calls."""

from .models import (
    Contract,
    Decision,
    Event,
    Evidence,
    ThesisVersion,
    TradePlan,
)


def unique_facts[T: Contract](facts: tuple[T, ...], identity: str) -> tuple[T, ...]:
    unique: dict[str, T] = {}
    for fact in facts:
        key = str(getattr(fact, identity))
        if key in unique and unique[key] != fact:
            raise ValueError(f"conflicting {identity}: {key}")
        unique[key] = fact
    return tuple(unique.values())


def validate_context(
    record: Decision | TradePlan,
    event: Event,
    evidence: tuple[Evidence, ...],
) -> None:
    at = record.at if isinstance(record, Decision) else record.created_at
    if record.event_id != event.id or at < event.detected_at:
        raise ValueError("record does not match detected event")
    if isinstance(record, TradePlan) and record.symbol != event.symbol:
        raise ValueError("plan symbol differs from event")
    sources = {e.id: e for e in unique_facts(evidence, "id")}
    if len(set(record.evidence_ids)) != len(record.evidence_ids):
        raise ValueError("duplicate evidence reference")
    for ref in record.evidence_ids:
        item = sources.get(ref)
        if item is None or item.event_id != event.id:
            raise ValueError("missing or mismatched evidence")
        if item.version_available_at > at:
            raise ValueError("evidence version unavailable at decision time")


def validate_revision(current: ThesisVersion, previous: ThesisVersion | None) -> None:
    if previous is None:
        if current.version != 1 or current.previous_id is not None:
            raise ValueError("initial thesis must start at version one")
    elif (
        current.id == previous.id
        or current.plan_id != previous.plan_id
        or current.previous_id != previous.id
        or current.version != previous.version + 1
        or current.at <= previous.at
    ):
        raise ValueError("invalid append-only thesis revision")
