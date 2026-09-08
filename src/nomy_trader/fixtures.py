"""Explicit hypothetical fixtures; never production policy defaults."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TypedDict

from .domain.models import (
    Action,
    Category,
    Decision,
    Event,
    Evidence,
    PipelineHealth,
    Recommendation,
    RecommendationPolicy,
    SizingInputs,
    SuggestedSize,
)
from .scenarios import AT, event, evidence, plan


class ValidationContext(TypedDict):
    recommendation: Recommendation
    decision: Decision
    event: Event
    evidence: tuple[Evidence, ...]
    policy: RecommendationPolicy
    health: PipelineHealth
    now: datetime


def context() -> ValidationContext:
    inputs = SizingInputs(
        policy_version="fixture-v1",
        source="Hypothetical fixture, not actual capital",
        as_of=AT,
        valid_until=AT + timedelta(days=1),
        currency="USD",
        reference_capital=Decimal("10000"),
        risk_budget=Decimal("25"),
        maximum_notional=Decimal("500"),
        quantity_increment=Decimal("1"),
    )
    size = SuggestedSize(
        inputs=inputs,
        quantity=Decimal("5"),
        notional=Decimal("500"),
        loss_at_stop=Decimal("25"),
        calculation_version="fixture-v1",
    )
    return ValidationContext(
        recommendation=Recommendation(
            id="rec-1",
            schema_version="1",
            idempotency_key="synthetic:1",
            plan=plan(),
            decision_id="decision-1",
            quote_as_of=AT,
            created_at=AT,
            expires_at=AT + timedelta(seconds=600),
            sizing=size,
        ),
        decision=Decision(
            id="decision-1",
            event_id="event-1",
            at=AT,
            action=Action.PROPOSE_BUY,
            category=Category.TEMPORARY,
            evidence_ids=("evidence-1",),
            rationale="Synthetic premise",
            confidence=Decimal("0.5"),
            uncertainty="Synthetic only",
            strategy_version="fixture-v1",
            model_version="none",
            prompt_version="none",
        ),
        event=event(),
        evidence=(evidence(),),
        policy=RecommendationPolicy(
            version="fixture-v1",
            maximum_quote_age_seconds=300,
            maximum_recommendation_age_seconds=600,
            minimum_margin_of_safety=Decimal("0.05"),
            portfolio_limits="unavailable",
        ),
        health=PipelineHealth(
            data_available=True,
            evidence_available=True,
            model_available=True,
            persistence_available=True,
            quota_available=True,
        ),
        now=AT,
    )
