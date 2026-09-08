"""Pure aggregate validation. No state mutations or provider calls."""

from datetime import datetime

from .models import (
    Action,
    Contract,
    Decision,
    Event,
    Evidence,
    PipelineHealth,
    Recommendation,
    RecommendationPolicy,
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


def validate_recommendation(
    recommendation: Recommendation,
    decision: Decision,
    event: Event,
    evidence: tuple[Evidence, ...],
    policy: RecommendationPolicy,
    health: PipelineHealth,
    now: datetime,
) -> None:
    """Check complete context before persistence/delivery; no external effects.

    Validity is evaluated against an explicit clock. Sizing arithmetic is checked
    but final quantity selection belongs to the deterministic sizing module.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("validation clock must be timezone-aware")
    if not all(health.model_dump().values()):
        raise ValueError("recommendation pipeline unavailable")
    plan = recommendation.plan
    validate_context(plan, event, evidence)
    validate_context(decision, event, evidence)
    if decision.action != Action.PROPOSE_BUY:
        raise ValueError("recommendation requires a buy proposal")
    if recommendation.decision_id != decision.id or decision.at > plan.created_at:
        raise ValueError("recommendation does not match decision")
    if not set(decision.evidence_ids).issubset(plan.evidence_ids):
        raise ValueError("plan omits decision evidence")
    for field in ("strategy_version", "model_version", "prompt_version"):
        if getattr(plan, field) != getattr(decision, field):
            raise ValueError("plan and decision versions differ")
    if now < recommendation.created_at or now >= recommendation.expires_at:
        raise ValueError("recommendation not yet valid or expired")
    if (now - recommendation.quote_as_of).total_seconds() > (
        policy.maximum_quote_age_seconds
    ):
        raise ValueError("stale quote")
    if (now - recommendation.created_at).total_seconds() > (
        policy.maximum_recommendation_age_seconds
    ):
        raise ValueError("stale recommendation")
    # Current recommendations need evidence actually retrieved before analysis.
    # validate_context alone also supports documented historical archives.
    sources = {e.id: e for e in evidence}
    for ref in plan.evidence_ids:
        deadline = decision.at if ref in decision.evidence_ids else plan.created_at
        if sources[ref].retrieved_at > deadline:
            raise ValueError("evidence not retrieved before analysis")
    size = recommendation.sizing
    inputs = size.inputs
    if inputs.policy_version != policy.version:
        raise ValueError("sizing policy version mismatch")
    if not inputs.as_of <= plan.created_at <= now < inputs.valid_until:
        raise ValueError("sizing inputs unavailable or expired")
    if size.notional != size.quantity * plan.entry_ceiling:
        raise ValueError("incorrect suggested notional")
    if size.loss_at_stop != size.quantity * (plan.entry_ceiling - plan.stop):
        raise ValueError("incorrect advisory stop loss")
    if size.quantity % inputs.quantity_increment != 0:
        raise ValueError("quantity violates rounding increment")
    if (
        size.notional > inputs.maximum_notional
        or size.loss_at_stop > inputs.risk_budget
    ):
        raise ValueError("suggested size exceeds advisory budget")
    margin = (plan.valuation.fair_value.low - plan.entry_ceiling) / (
        plan.valuation.fair_value.low
    )
    if margin < policy.minimum_margin_of_safety:
        raise ValueError("insufficient margin of safety")
