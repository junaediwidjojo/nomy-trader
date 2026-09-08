"""Fixed synthetic facts, not market analysis or strategy recommendations."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from .domain.models import (
    Acknowledgement,
    Action,
    Category,
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
    TradePlan,
)
from .domain.validation import reconcile, validate_context, validate_execution

AT = datetime(2026, 1, 5, 16, tzinfo=UTC)


def event() -> Event:
    return Event(
        id="event-1",
        symbol="SYNTH",
        detected_at=AT,
        market_at=AT,
        return_fraction=Decimal("-0.1"),
        standardized_move=Decimal("-3"),
        relative_volume=Decimal("2"),
        origin="synthetic",
        deduplication_key="synthetic-1",
    )


def evidence() -> Evidence:
    return Evidence(
        id="evidence-1",
        event_id="event-1",
        kind="fixture",
        source="synthetic:1",
        publisher="Synthetic publisher",
        published_at=AT,
        retrieved_at=AT,
        version_available_at=AT,
        availability_proof="Fixed fixture snapshot",
        content_hash="a" * 64,
        content_or_licensed_reference="Synthetic source text",
        primary=True,
    )


def plan() -> TradePlan:
    return TradePlan.model_validate(
        {
            "id": "plan-1",
            "event_id": "event-1",
            "symbol": "SYNTH",
            "created_at": AT,
            "evidence_ids": ["evidence-1"],
            "entry_ceiling": "100",
            "valuation": {
                "bear": "90",
                "base": "120",
                "bull": "140",
                "fair_value": {"low": "110", "high": "130"},
                "formula": "Synthetic supplied values; no valuation calculation",
                "assumptions": ["Fixture assumptions"],
            },
            "target": {"low": "110", "high": "120"},
            "stop": "95",
            "expected_calendar_days": 5,
            "maximum_calendar_days": 10,
            "exit_policy": "Synthetic full exit at target, stop, invalidation or expiry",
            "thesis": "Synthetic temporary interruption",
            "assumptions": ["Recovery"],
            "invalidations": ["Permanent shutdown"],
            "confidence": "0.5",
            "uncertainty": "Synthetic only",
            "strategy_version": "fixture-v1",
            "model_version": "none",
            "prompt_version": "none",
        }
    )


def health() -> Health:
    return Health(
        broker_connected=True,
        data_fresh=True,
        protection_ok=True,
        risk_ok=True,
        model_available=True,
    )


def order() -> Order:
    return Order(
        id="order-1",
        idempotency_key="intent-1",
        plan_id="plan-1",
        symbol="SYNTH",
        side="BUY",
        quantity=Decimal("10"),
        kind="LIMIT",
        limit_price=Decimal("100"),
        state=OrderState.PARTIALLY_FILLED,
        at=AT,
    )


def execution() -> tuple[Fill, Acknowledgement]:
    return (
        Fill(
            execution_id="exec-1",
            order_id="order-1",
            symbol="SYNTH",
            side="BUY",
            quantity=Decimal("4"),
            price=Decimal("99"),
            commission=None,
            at=AT,
        ),
        Acknowledgement(
            id="ack-1",
            order_id="order-1",
            broker_order_id="synthetic-1",
            state=OrderState.ACKNOWLEDGED,
            at=AT,
        ),
    )


def classification(
    category: Category, action: Action, with_evidence: bool = True
) -> bool:
    decision = Decision(
        id="decision-1",
        event_id="event-1",
        at=AT,
        action=action,
        category=category,
        evidence_ids=("evidence-1",) if with_evidence else (),
        rationale="Given synthetic classification, not inferred",
        confidence=Decimal("0.5"),
        uncertainty="Synthetic only",
        strategy_version="fixture-v1",
        model_version="none",
        prompt_version="none",
    )
    validate_context(decision, event(), (evidence(),))
    return decision.action == action


def temporary() -> bool:
    validate_context(plan(), event(), (evidence(),))
    return classification(Category.TEMPORARY, Action.PROPOSE_BUY)


def late() -> bool:
    data = evidence().model_dump()
    data.update(version_available_at=AT.replace(day=6), retrieved_at=AT.replace(day=6))
    try:
        validate_context(plan(), event(), (Evidence.model_validate(data),))
    except ValueError:
        return True
    return False


def duplicate() -> bool:
    fill, ack = execution()
    fills, acks = validate_execution(order(), (fill, fill), (ack, ack))
    return len(fills) == len(acks) == 1 and fills[0].quantity == 4


def stale() -> bool:
    h = Health.model_validate({**health().model_dump(), "data_fresh": False})
    return not reconcile((), (), (), h).new_orders_allowed


def model_outage() -> bool:
    h = Health.model_validate(
        {**health().model_dump(), "model_available": False, "protection_ok": False}
    )
    return "HEALTH:protection_ok" in reconcile((), (), (), h).issues


def mismatch() -> bool:
    position = PositionSnapshot(symbol="SYNTH", quantity=Decimal("4"), at=AT)
    internal = PlanPosition(
        plan_id="plan-1", symbol="SYNTH", state=PlanState.OPEN, quantity=Decimal("5")
    )
    return not reconcile((position,), (internal,), (), health()).new_orders_allowed


SCENARIOS: tuple[tuple[str, Callable[[], bool]], ...] = (
    ("temporary operational issue and recovery premise", temporary),
    (
        "permanent guidance reduction",
        lambda: classification(Category.CORRECT_REPRICING, Action.REJECT),
    ),
    (
        "fraud or governance allegation",
        lambda: classification(Category.GOVERNANCE, Action.REJECT),
    ),
    ("sector-wide panic", lambda: classification(Category.MARKET_SECTOR, Action.WAIT)),
    (
        "no identifiable news",
        lambda: classification(Category.UNCERTAIN, Action.WAIT, False),
    ),
    ("conflicting sources", lambda: classification(Category.UNCERTAIN, Action.WAIT)),
    ("late or revised evidence", late),
    ("stale price data", stale),
    ("partial fill and duplicate acknowledgement", duplicate),
    ("model outage while position monitoring fails protection", model_outage),
    ("broker/database mismatch", mismatch),
)


def main() -> int:
    failures = 0
    for name, run in SCENARIOS:
        try:
            passed = run()
        except Exception as exc:
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        print(f"{'PASS' if passed else 'FAIL'} {name}")
        failures += not passed
    print(f"{len(SCENARIOS) - failures}/{len(SCENARIOS)} synthetic scenarios passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
