"""Fixed synthetic facts, not market analysis or strategy recommendations."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from .domain.models import (
    Action,
    Category,
    Decision,
    Event,
    Evidence,
    TradePlan,
)
from .domain.validation import validate_context

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
            "exit_policy": "Synthetic advisory exit at target, stop or expiry",
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


def unavailable(flag: str) -> bool:
    # Import lazily so the fixture builders can reuse this module's source facts.
    from .domain.models import PipelineHealth
    from .domain.validation import validate_recommendation
    from .fixtures import context

    args = context()
    args["health"] = PipelineHealth.model_validate(
        {**args["health"].model_dump(), flag: False}
    )
    try:
        validate_recommendation(**args)
    except ValueError:
        return True
    return False


def stale_quote() -> bool:
    from datetime import timedelta

    from .domain.validation import validate_recommendation
    from .fixtures import context

    args = context()
    args["now"] += timedelta(seconds=301)
    try:
        validate_recommendation(**args)
    except ValueError:
        return True
    return False


def ambiguous_notification() -> bool:
    from .domain.models import DeliveryStatus, NotificationAttempt

    attempt = NotificationAttempt(
        id="attempt-1",
        recommendation_id="rec-1",
        status=DeliveryStatus.UNKNOWN,
        attempted_at=AT,
        recorded_at=AT,
    )
    return attempt.sent_at is None and attempt.provider_message_id is None


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
    ("stale quote blocks recommendation", stale_quote),
    ("quota unavailable blocks recommendation", lambda: unavailable("quota_available")),
    ("model outage blocks recommendation", lambda: unavailable("model_available")),
    (
        "persistence unavailable blocks recommendation",
        lambda: unavailable("persistence_available"),
    ),
    ("ambiguous notification is not confirmed sent", ambiguous_notification),
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
