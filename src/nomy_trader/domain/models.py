"""Boundary models. Validation establishes consistency, never order authority."""

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
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    RAISE_STOP = "RAISE_STOP"


class Category(StrEnum):
    NOISE = "NOISE"
    TEMPORARY = "TEMPORARY"
    UNCERTAIN = "UNCERTAIN"
    STRUCTURAL = "STRUCTURAL"
    GOVERNANCE = "GOVERNANCE"
    CORRECT_REPRICING = "CORRECT_REPRICING"
    MARKET_SECTOR = "MARKET_SECTOR"


class PlanState(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ENTRY_PENDING = "ENTRY_PENDING"
    OPEN = "OPEN"
    REDUCING = "REDUCING"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RECONCILIATION_HOLD = "RECONCILIATION_HOLD"


class OrderState(StrEnum):
    PROPOSED = "PROPOSED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


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
    state: PlanState = PlanState.DRAFT

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


class Order(Contract):
    id: Text
    idempotency_key: Text
    plan_id: Text
    symbol: Text
    side: Literal["BUY", "SELL"]
    quantity: Positive
    kind: Literal["LIMIT", "STOP", "MARKET"]
    limit_price: Positive | None = None
    stop_price: Positive | None = None
    state: OrderState
    at: Timestamp
    mode: Literal["paper"] = "paper"

    @model_validator(mode="after")
    def prices(self) -> Self:
        if (self.limit_price is not None) != (self.kind == "LIMIT"):
            raise ValueError("limit price must match order kind")
        if (self.stop_price is not None) != (self.kind == "STOP"):
            raise ValueError("stop price must match order kind")
        return self


class Acknowledgement(Contract):
    id: Text
    order_id: Text
    broker_order_id: Text
    state: OrderState
    at: Timestamp


class Fill(Contract):
    execution_id: Text
    order_id: Text
    symbol: Text
    side: Literal["BUY", "SELL"]
    quantity: Positive
    price: Positive
    commission: Nonnegative | None
    at: Timestamp


class PositionSnapshot(Contract):
    symbol: Text
    quantity: Nonnegative
    at: Timestamp


class PlanPosition(Contract):
    plan_id: Text
    symbol: Text
    state: PlanState
    quantity: Nonnegative


class Health(Contract):
    broker_connected: bool
    data_fresh: bool
    protection_ok: bool
    risk_ok: bool
    model_available: bool
    mode: Literal["paper"] = "paper"


class ReconciliationResult(Contract):
    issues: tuple[Text, ...]

    @property
    def new_orders_allowed(self) -> bool:
        """Necessary health condition only; never execution authorization."""
        return not self.issues
