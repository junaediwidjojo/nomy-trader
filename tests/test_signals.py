from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from nomy_trader.research import (
    BusinessRiskKind,
    BusinessRiskObservation,
    ObservationStatus,
    evaluate_business_gate,
)
from nomy_trader.signals import (
    MarketCondition,
    MarketConfirmation,
    MarketGateStatus,
    SignalOutcomeStatus,
    TradingAgentsReview,
    TradingAgentsReviewStatus,
    ValuationInputs,
    calculate_price_signal,
    compose_signal_outcome,
    evaluate_market_gate,
    run_price_signal_fixture,
    validate_tradingagents_review,
)
from tests.test_research import packet


def inputs(**changes: object) -> ValuationInputs:
    values: dict[str, object] = {
        "symbol": "BRZE",
        "as_of": datetime(2026, 9, 9, tzinfo=UTC),
        "evidence_ids": ("earnings",),
        "bear_fair_value": Decimal("30"),
        "base_fair_value": Decimal("36"),
        "bull_fair_value": Decimal("42"),
        "margin_of_safety": Decimal("0.20"),
        "entry_zone_width": Decimal("0.05"),
        "formula_version": "valuation-v1",
        "assumptions": ("Illustrative fixture.",),
    }
    values.update(changes)
    return ValuationInputs(**values)


def test_price_signal_uses_bear_value_and_explicit_margin() -> None:
    signal = calculate_price_signal(inputs())

    assert signal.entry_ceiling == Decimal("24")
    assert signal.entry_zone.low == Decimal("22.80")
    assert signal.entry_zone.high == Decimal("24")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bear_fair_value", Decimal("0")),
        ("margin_of_safety", Decimal("1")),
        ("entry_zone_width", Decimal("0")),
        ("base_fair_value", Decimal("20")),
    ],
)
def test_inputs_reject_invalid_values(field: str, value: object) -> None:
    with pytest.raises((ValidationError, ValueError)):
        inputs(**{field: value})


def market_confirmation(**changes: object) -> MarketConfirmation:
    values: dict[str, object] = {
        "symbol": "BRZE",
        "provider": "fixture",
        "venue_limitation": "Illustrative delayed quote.",
        "quote_as_of": datetime(2026, 9, 9, 10, tzinfo=UTC),
        "checked_at": datetime(2026, 9, 9, 10, 1, tzinfo=UTC),
        "reference_price": Decimal("24.52"),
        "maximum_age_seconds": 120,
        "conditions": (MarketCondition(name="volume", passed=True, detail="present"),),
    }
    values.update(changes)
    return MarketConfirmation(**values)


def review(**changes: object) -> TradingAgentsReview:
    values: dict[str, object] = {
        "symbol": "BRZE",
        "reviewed_at": datetime(2026, 9, 9, 10, 2, tzinfo=UTC),
        "status": TradingAgentsReviewStatus.SUPPORTS,
        "summary": "The cited evidence supports a temporary decline thesis.",
        "report_hash": "b" * 64,
        "evidence_ids": ("filing",),
    }
    values.update(changes)
    return TradingAgentsReview(**values)


def test_market_gate_blocks_stale_or_failed_conditions() -> None:
    stale = evaluate_market_gate(
        market_confirmation(checked_at=datetime(2026, 9, 9, 10, 3, tzinfo=UTC))
    )
    failed = evaluate_market_gate(
        market_confirmation(
            conditions=(MarketCondition(name="volume", passed=False, detail="thin"),)
        )
    )

    assert stale.status == MarketGateStatus.BLOCKED
    assert stale.blocking_reasons == ("quote_stale",)
    assert failed.blocking_reasons == ("market_condition_failed:volume",)


def test_review_requires_available_packet_evidence() -> None:
    validate_tradingagents_review(review(), packet())
    with pytest.raises(ValueError, match="outside packet"):
        validate_tradingagents_review(review(evidence_ids=("other",)), packet())
    with pytest.raises(ValidationError, match="cannot claim report evidence"):
        review(
            status=TradingAgentsReviewStatus.UNAVAILABLE,
            report_hash="b" * 64,
            evidence_ids=(),
        )


def test_composed_outcome_is_conservative() -> None:
    ready_business = evaluate_business_gate(packet())
    ready_market = evaluate_market_gate(market_confirmation())

    candidate = compose_signal_outcome(ready_business, ready_market, review())
    challenged = compose_signal_outcome(
        ready_business,
        ready_market,
        review(status=TradingAgentsReviewStatus.CHALLENGES),
    )
    rejected = compose_signal_outcome(
        evaluate_business_gate(packet(ObservationStatus.UNKNOWN)),
        ready_market,
        review(),
    )

    assert candidate.status == SignalOutcomeStatus.MANUAL_BUY_CANDIDATE
    assert challenged.status == SignalOutcomeStatus.WATCH
    assert rejected.status == SignalOutcomeStatus.REJECT


def test_structural_risk_and_missing_event_are_rejected() -> None:
    clean_packet = packet()
    structural_packet = clean_packet.model_copy(
        update={
            "observations": tuple(
                BusinessRiskObservation(
                    kind=observation.kind,
                    status=(
                        ObservationStatus.PRESENT
                        if observation.kind == BusinessRiskKind.GOING_CONCERN
                        else observation.status
                    ),
                    evidence_ids=observation.evidence_ids,
                    assessed_at=observation.assessed_at,
                )
                for observation in clean_packet.observations
            )
        }
    )

    structural = evaluate_business_gate(structural_packet)
    no_event = evaluate_business_gate(packet(ObservationStatus.UNKNOWN))

    assert structural.blocking_reasons == ("going_concern_present",)
    assert no_event.blocking_reasons == ("event_explanation_missing_or_unresolved",)


def test_malformed_review_and_unavailable_review_cannot_promote() -> None:
    with pytest.raises(ValidationError, match="requires report hash"):
        review(report_hash=None)

    outcome = compose_signal_outcome(
        evaluate_business_gate(packet()),
        evaluate_market_gate(market_confirmation()),
        review(
            status=TradingAgentsReviewStatus.UNAVAILABLE,
            summary="The provider timed out before returning a report.",
            report_hash=None,
            evidence_ids=(),
        ),
    )

    assert outcome.status == SignalOutcomeStatus.WATCH
    assert outcome.reasons == ("tradingagents_review_unavailable",)


def test_offline_workflow_requires_consistent_cited_stages() -> None:
    from nomy_trader.signals import PriceSignalFixture

    result = run_price_signal_fixture(
        PriceSignalFixture(
            evidence_packet=packet(),
            valuation=inputs(),
            market_confirmation=market_confirmation(),
            tradingagents_review=review(),
        )
    )

    assert result.outcome.status == SignalOutcomeStatus.MANUAL_BUY_CANDIDATE
    assert result.price_signal.entry_ceiling == Decimal("24")
