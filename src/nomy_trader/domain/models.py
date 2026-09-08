"""Boundary models establish consistency, never delivery/execution authority."""

from datetime import UTC
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

Text = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Finite = Annotated[Decimal, Field(allow_inf_nan=False)]
Confidence = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]
Timestamp = Annotated[AwareDatetime, AfterValidator(lambda v: v.astimezone(UTC))]
References = Annotated[tuple[Text, ...], Field(min_length=1)]
Days = Annotated[int, Field(strict=True, gt=0)]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)


class Action(StrEnum):
    REJECT = "REJECT"
    WAIT = "WAIT"
    PROPOSE_BUY = "PROPOSE_BUY"


class Category(StrEnum):
    NOISE = "NOISE"
    TEMPORARY = "TEMPORARY"
    UNCERTAIN = "UNCERTAIN"
    STRUCTURAL = "STRUCTURAL"
    GOVERNANCE = "GOVERNANCE"
    CORRECT_REPRICING = "CORRECT_REPRICING"
    MARKET_SECTOR = "MARKET_SECTOR"


class Event(Contract):
    id: Text
    symbol: Text
    detected_at: Timestamp
    market_at: Timestamp
    return_fraction: Finite
    standardized_move: Finite
    relative_volume: Nonnegative
    origin: Text
    deduplication_key: Text

    @model_validator(mode="after")
    def chronology(self) -> Self:
        if self.market_at > self.detected_at:
            raise ValueError("market timestamp follows detection")
        return self


class Evidence(Contract):
    id: Text
    event_id: Text
    kind: Text
    source: Text
    publisher: Text
    published_at: Timestamp
    retrieved_at: Timestamp
    version_available_at: Timestamp
    availability_proof: Text
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    content_or_licensed_reference: Text
    primary: bool

    @model_validator(mode="after")
    def chronology(self) -> Self:
        if not self.published_at <= self.version_available_at <= self.retrieved_at:
            raise ValueError("invalid source version chronology")
        return self


class Decision(Contract):
    id: Text
    event_id: Text
    at: Timestamp
    action: Action
    category: Category
    evidence_ids: tuple[Text, ...]
    rationale: Text
    confidence: Confidence
    uncertainty: Text
    strategy_version: Text
    model_version: Text
    prompt_version: Text

    @model_validator(mode="after")
    def supported(self) -> Self:
        if self.action == Action.PROPOSE_BUY and (
            not self.evidence_ids
            or self.category not in (Category.NOISE, Category.TEMPORARY)
        ):
            raise ValueError("buy proposal requires evidence and eligible category")
        return self


class PriceRange(Contract):
    low: Positive
    high: Positive

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.low > self.high:
            raise ValueError("inverted price range")
        return self


class Valuation(Contract):
    bear: Positive
    base: Positive
    bull: Positive
    fair_value: PriceRange
    formula: Text
    assumptions: References

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not self.bear <= self.base <= self.bull:
            raise ValueError("unordered valuation scenarios")
        return self


class TradePlan(Contract):
    id: Text
    event_id: Text
    symbol: Text
    created_at: Timestamp
    evidence_ids: References
    entry_ceiling: Positive
    valuation: Valuation
    target: PriceRange
    stop: Positive
    expected_calendar_days: Days
    maximum_calendar_days: Days
    exit_policy: Text
    thesis: Text
    assumptions: References
    invalidations: References
    confidence: Confidence
    uncertainty: Text
    strategy_version: Text
    model_version: Text
    prompt_version: Text

    @model_validator(mode="after")
    def exits(self) -> Self:
        if self.stop >= self.entry_ceiling:
            raise ValueError("stop must be below entry ceiling")
        if self.expected_calendar_days > self.maximum_calendar_days:
            raise ValueError("expected duration exceeds maximum")
        return self


class ThesisVersion(Contract):
    id: Text
    plan_id: Text
    version: Days
    previous_id: Text | None
    at: Timestamp
    evidence_ids: References
    thesis: Text
    assumptions: References
    changed_assumptions: tuple[Text, ...]


class SizingInputs(Contract):
    """Explicit policy inputs; no capital or risk defaults are supplied."""

    policy_version: Text
    source: Text
    as_of: Timestamp
    valid_until: Timestamp
    currency: Literal["USD"]
    reference_capital: Positive
    risk_budget: Positive
    maximum_notional: Positive
    quantity_increment: Positive

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.valid_until <= self.as_of:
            raise ValueError("sizing input validity must follow its as-of time")
        if max(self.risk_budget, self.maximum_notional) > self.reference_capital:
            raise ValueError("advisory budgets exceed reference capital")
        return self


class SuggestedSize(Contract):
    """Output supplied by deterministic sizing, never part of analyst output."""

    inputs: SizingInputs
    quantity: Positive
    notional: Positive
    loss_at_stop: Positive
    calculation_version: Text


class Recommendation(Contract):
    id: Text
    schema_version: Literal["1"]
    idempotency_key: Text
    plan: TradePlan
    decision_id: Text
    quote_as_of: Timestamp
    created_at: Timestamp
    expires_at: Timestamp
    sizing: SuggestedSize

    @model_validator(mode="after")
    def chronology(self) -> Self:
        if not self.quote_as_of <= self.plan.created_at <= self.created_at:
            raise ValueError("invalid recommendation chronology")
        if self.expires_at <= self.created_at:
            raise ValueError("recommendation expiry must follow creation")
        return self


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class NotificationAttempt(Contract):
    """Immutable attempt snapshot. SENT means acknowledged by Telegram only."""

    id: Text
    recommendation_id: Text
    status: DeliveryStatus
    recorded_at: Timestamp
    attempted_at: Timestamp | None = None
    sent_at: Timestamp | None = None
    provider_message_id: Text | None = None
    error_code: Text | None = None

    @model_validator(mode="after")
    def delivery_facts(self) -> Self:
        if self.status == DeliveryStatus.PENDING:
            if self.attempted_at is not None:
                raise ValueError("pending notification has not been attempted")
        elif self.attempted_at is None:
            raise ValueError("attempted notification requires attempt time")
        if self.attempted_at is not None and self.attempted_at > self.recorded_at:
            raise ValueError("attempt follows recorded time")
        if self.status == DeliveryStatus.SENT:
            if self.sent_at is None or self.provider_message_id is None:
                raise ValueError("sent requires provider acknowledgement")
            if self.attempted_at is None or not (
                self.attempted_at <= self.sent_at <= self.recorded_at
            ):
                raise ValueError("invalid send chronology")
        elif self.sent_at is not None or self.provider_message_id is not None:
            raise ValueError("unconfirmed notification cannot contain sent facts")
        return self


class RecommendationPolicy(Contract):
    """Required policy context. No market/risk threshold is guessed here."""

    version: Text
    maximum_quote_age_seconds: Days
    maximum_recommendation_age_seconds: Days
    minimum_margin_of_safety: Confidence
    portfolio_limits: Literal["unavailable"]


class PipelineHealth(Contract):
    data_available: Annotated[bool, Field(strict=True)]
    evidence_available: Annotated[bool, Field(strict=True)]
    model_available: Annotated[bool, Field(strict=True)]
    persistence_available: Annotated[bool, Field(strict=True)]
    quota_available: Annotated[bool, Field(strict=True)]
