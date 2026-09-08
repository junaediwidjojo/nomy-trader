"""Pure aggregate validation. No state mutations or provider calls."""

from typing import TypeVar

from .models import (
    Acknowledgement,
    Contract,
    Decision,
    Event,
    Evidence,
    Fill,
    Health,
    Order,
    OrderState,
    PlanPosition,
    PlanState,
    PositionSnapshot,
    ReconciliationResult,
    ThesisVersion,
    TradePlan,
)

T = TypeVar("T", bound=Contract)


def unique_facts(facts: tuple[T, ...], identity: str) -> tuple[T, ...]:
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


def validate_execution(
    order: Order,
    fills: tuple[Fill, ...],
    acknowledgements: tuple[Acknowledgement, ...],
) -> tuple[tuple[Fill, ...], tuple[Acknowledgement, ...]]:
    fills = unique_facts(fills, "execution_id")
    acknowledgements = unique_facts(acknowledgements, "id")
    for fill in fills:
        if (
            fill.order_id != order.id
            or fill.symbol != order.symbol
            or fill.side != order.side
            or fill.at < order.at
        ):
            raise ValueError("fill does not match order")
    if sum(f.quantity for f in fills) > order.quantity:
        raise ValueError("fills exceed order quantity")
    broker_ids = set()
    for ack in acknowledgements:
        if ack.order_id != order.id or ack.at < order.at:
            raise ValueError("acknowledgement does not match order")
        broker_ids.add(ack.broker_order_id)
    if len(broker_ids) > 1:
        raise ValueError("multiple broker orders for one internal order")
    return fills, acknowledgements


ACTIVE = frozenset(
    {
        PlanState.ENTRY_PENDING,
        PlanState.OPEN,
        PlanState.REDUCING,
        PlanState.RECONCILIATION_HOLD,
    }
)


def reconcile(
    positions: tuple[PositionSnapshot, ...],
    plans: tuple[PlanPosition, ...],
    orders: tuple[Order, ...],
    health: Health,
) -> ReconciliationResult:
    issues: set[str] = set()
    for name in ("broker_connected", "data_fresh", "protection_ok", "risk_ok"):
        if not getattr(health, name):
            issues.add(f"HEALTH:{name}")
    if any(o.state == OrderState.UNKNOWN for o in orders):
        issues.add("UNKNOWN_SUBMISSION")
    if len({p.symbol for p in positions}) != len(positions):
        issues.add("DUPLICATE_BROKER_SYMBOL")
    if len({p.plan_id for p in plans}) != len(plans):
        issues.add("DUPLICATE_PLAN_ID")
    active = [p for p in plans if p.state in ACTIVE]
    for plan in active:
        if plan.state == PlanState.RECONCILIATION_HOLD:
            issues.add(f"RECONCILIATION_HOLD:{plan.plan_id}")
    for position in positions:
        if not position.quantity:
            continue
        matches = [p for p in active if p.symbol == position.symbol]
        if len(matches) != 1:
            issues.add(f"PLAN_MAPPING:{position.symbol}")
        elif matches[0].quantity != position.quantity:
            issues.add(f"QUANTITY_MISMATCH:{position.symbol}")
    held = {p.symbol for p in positions if p.quantity}
    for plan in active:
        if plan.symbol not in held:
            issues.add(f"ORDER_HISTORY_REQUIRED:{plan.plan_id}")
    return ReconciliationResult(issues=tuple(sorted(issues)))
