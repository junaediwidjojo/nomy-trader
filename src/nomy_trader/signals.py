"""Deterministic price-signal contracts and calculations."""

from decimal import Decimal
from enum import StrEnum

from pydantic import Field, model_validator

from nomy_trader.domain.models import (
    Contract,
    Positive,
    PriceRange,
    References,
    Text,
    Timestamp,
)
from nomy_trader.research import (
    EvidencePacket,
    ResearchGateResult,
    ResearchGateStatus,
    evaluate_business_gate,
)


class ValuationInputs(Contract):
    symbol: Text
    as_of: Timestamp
    evidence_ids: References
    bear_fair_value: Positive
    base_fair_value: Positive
    bull_fair_value: Positive
    margin_of_safety: Decimal = Field(gt=0, lt=1, allow_inf_nan=False)
    entry_zone_width: Decimal = Field(gt=0, lt=1, allow_inf_nan=False)
    formula_version: Text
    assumptions: References

    @model_validator(mode="after")
    def scenarios_are_ordered(self) -> "ValuationInputs":
        if not self.bear_fair_value <= self.base_fair_value <= self.bull_fair_value:
            raise ValueError("valuation scenarios must be ordered")
        return self


class PriceSignal(Contract):
    symbol: Text
    as_of: Timestamp
    evidence_ids: References
    fair_value: PriceRange
    entry_zone: PriceRange
    entry_ceiling: Positive
    formula: Text
    assumptions: References


def calculate_price_signal(inputs: ValuationInputs) -> PriceSignal:
    """Derive an entry ceiling only from explicit valuation assumptions."""
    ceiling = inputs.bear_fair_value * (Decimal("1") - inputs.margin_of_safety)
    zone_low = ceiling * (Decimal("1") - inputs.entry_zone_width)
    return PriceSignal(
        symbol=inputs.symbol,
        as_of=inputs.as_of,
        evidence_ids=inputs.evidence_ids,
        fair_value=PriceRange(low=inputs.bear_fair_value, high=inputs.bull_fair_value),
        entry_zone=PriceRange(low=zone_low, high=ceiling),
        entry_ceiling=ceiling,
        formula=(
            "entry_ceiling = bear_fair_value * (1 - margin_of_safety); "
            "entry_zone = [entry_ceiling * (1 - entry_zone_width), entry_ceiling]"
        ),
        assumptions=inputs.assumptions,
    )


class MarketCondition(Contract):
    """One explicitly configured market check; no indicator is implicit."""

    name: Text
    passed: bool
    detail: Text


class MarketConfirmation(Contract):
    """A provider-labelled quote snapshot used only to gate a price signal."""

    symbol: Text
    provider: Text
    venue_limitation: Text
    quote_as_of: Timestamp
    checked_at: Timestamp
    reference_price: Positive
    maximum_age_seconds: int = Field(strict=True, gt=0)
    conditions: tuple[MarketCondition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def quote_precedes_check_and_conditions_are_unique(self) -> "MarketConfirmation":
        if self.quote_as_of > self.checked_at:
            raise ValueError("quote timestamp follows market check")
        names = [condition.name for condition in self.conditions]
        if len(names) != len(set(names)):
            raise ValueError("market conditions must be unique")
        return self


class MarketGateStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class MarketGateResult(Contract):
    status: MarketGateStatus
    blocking_reasons: tuple[Text, ...]


def evaluate_market_gate(confirmation: MarketConfirmation) -> MarketGateResult:
    """Block stale quotes or any failed, explicitly supplied market condition."""
    age_seconds = (confirmation.checked_at - confirmation.quote_as_of).total_seconds()
    reasons: list[str] = []
    if age_seconds > confirmation.maximum_age_seconds:
        reasons.append("quote_stale")
    reasons.extend(
        f"market_condition_failed:{condition.name}"
        for condition in confirmation.conditions
        if not condition.passed
    )
    return MarketGateResult(
        status=MarketGateStatus.BLOCKED if reasons else MarketGateStatus.READY,
        blocking_reasons=tuple(reasons),
    )


class TradingAgentsReviewStatus(StrEnum):
    SUPPORTS = "SUPPORTS"
    CHALLENGES = "CHALLENGES"
    UNAVAILABLE = "UNAVAILABLE"


class TradingAgentsReview(Contract):
    """Supplementary cited commentary, deliberately without price or action fields."""

    symbol: Text
    reviewed_at: Timestamp
    status: TradingAgentsReviewStatus
    summary: Text
    report_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence_ids: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def available_reviews_are_verifiable(self) -> "TradingAgentsReview":
        if self.status == TradingAgentsReviewStatus.UNAVAILABLE:
            if self.report_hash is not None or self.evidence_ids:
                raise ValueError("unavailable review cannot claim report evidence")
        elif self.report_hash is None or not self.evidence_ids:
            raise ValueError("available review requires report hash and evidence")
        return self


def validate_tradingagents_review(
    review: TradingAgentsReview, packet: EvidencePacket
) -> None:
    """Available commentary may refer only to facts in its curated packet."""
    if review.symbol != packet.symbol:
        raise ValueError("review symbol does not match evidence packet")
    packet_ids = {evidence.id for evidence in packet.evidence}
    if not set(review.evidence_ids).issubset(packet_ids):
        raise ValueError("review cites evidence outside packet")


class SignalOutcomeStatus(StrEnum):
    REJECT = "REJECT"
    WATCH = "WATCH"
    MANUAL_BUY_CANDIDATE = "MANUAL_BUY_CANDIDATE"


class SignalOutcome(Contract):
    status: SignalOutcomeStatus
    reasons: tuple[Text, ...]


def compose_signal_outcome(
    business_gate: ResearchGateResult,
    market_gate: MarketGateResult,
    review: TradingAgentsReview,
) -> SignalOutcome:
    """Combine independently evaluated stages conservatively and reproducibly."""
    if business_gate.status == ResearchGateStatus.BLOCKED:
        return SignalOutcome(
            status=SignalOutcomeStatus.REJECT,
            reasons=business_gate.blocking_reasons,
        )
    reasons = [*market_gate.blocking_reasons]
    if review.status == TradingAgentsReviewStatus.CHALLENGES:
        reasons.append("tradingagents_challenges_thesis")
    elif review.status == TradingAgentsReviewStatus.UNAVAILABLE:
        reasons.append("tradingagents_review_unavailable")
    if reasons:
        return SignalOutcome(status=SignalOutcomeStatus.WATCH, reasons=tuple(reasons))
    return SignalOutcome(
        status=SignalOutcomeStatus.MANUAL_BUY_CANDIDATE,
        reasons=("all_required_gates_passed",),
    )


class PriceSignalFixture(Contract):
    """Offline input for a complete, reproducible signal workflow demonstration."""

    evidence_packet: EvidencePacket
    valuation: ValuationInputs
    market_confirmation: MarketConfirmation
    tradingagents_review: TradingAgentsReview

    @model_validator(mode="after")
    def stages_describe_one_symbol(self) -> "PriceSignalFixture":
        symbols = {
            self.evidence_packet.symbol,
            self.valuation.symbol,
            self.market_confirmation.symbol,
            self.tradingagents_review.symbol,
        }
        if len(symbols) != 1:
            raise ValueError("all signal stages must use one symbol")
        return self


class PriceSignalWorkflowResult(Contract):
    price_signal: PriceSignal
    business_gate: ResearchGateResult
    market_gate: MarketGateResult
    outcome: SignalOutcome
    limitation: Text


def run_price_signal_fixture(fixture: PriceSignalFixture) -> PriceSignalWorkflowResult:
    """Run the pure workflow without providers, storage, or model invocation."""
    validate_tradingagents_review(fixture.tradingagents_review, fixture.evidence_packet)
    business_gate = evaluate_business_gate(fixture.evidence_packet)
    market_gate = evaluate_market_gate(fixture.market_confirmation)
    return PriceSignalWorkflowResult(
        price_signal=calculate_price_signal(fixture.valuation),
        business_gate=business_gate,
        market_gate=market_gate,
        outcome=compose_signal_outcome(
            business_gate, market_gate, fixture.tradingagents_review
        ),
        limitation=(
            "Offline fixture result only; it uses supplied facts and does not "
            "retrieve evidence, price data, or TradingAgents output."
        ),
    )


class CompletedSignal(Contract):
    """Immutable, reproducible record ready for the local SQLite journal."""

    id: Text
    recorded_at: Timestamp
    fixture: PriceSignalFixture
    result: PriceSignalWorkflowResult

    @model_validator(mode="after")
    def matches_the_deterministic_workflow(self) -> "CompletedSignal":
        if self.recorded_at < self.fixture.evidence_packet.as_of:
            raise ValueError("signal record precedes its evidence packet")
        expected = run_price_signal_fixture(self.fixture)
        if self.result != expected:
            raise ValueError("signal result does not match deterministic workflow")
        return self
