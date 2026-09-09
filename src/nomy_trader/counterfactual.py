"""Explicitly synthetic market scenarios; never recommendation inputs."""

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from nomy_trader.domain.models import Contract, Positive, References, Text, Timestamp


class ScenarioInput(Contract):
    """Supplied facts for an offline what-if exercise."""

    id: Text
    symbol: Text
    as_of: Timestamp
    base_observation_id: Text
    base_price: Positive
    hypothetical_price: Positive
    assumptions: References
    source_classification: Literal["SYNTHETIC"] = "SYNTHETIC"

    @model_validator(mode="after")
    def prices_differ(self) -> "ScenarioInput":
        if self.base_price == self.hypothetical_price:
            raise ValueError("hypothetical price must differ from base price")
        return self


class ScenarioResult(Contract):
    """A non-actionable comparison of supplied synthetic facts."""

    status: Literal["SCENARIO_ONLY"] = "SCENARIO_ONLY"
    scenario_id: Text
    symbol: Text
    as_of: Timestamp
    base_observation_id: Text
    base_price: Positive
    hypothetical_price: Positive
    price_change_fraction: Decimal = Field(allow_inf_nan=False)
    assumptions: References
    blocked_conclusions: References


def run_scenario(input_: ScenarioInput) -> ScenarioResult:
    """Calculate only the declared synthetic price comparison."""
    return ScenarioResult(
        scenario_id=input_.id,
        symbol=input_.symbol,
        as_of=input_.as_of,
        base_observation_id=input_.base_observation_id,
        base_price=input_.base_price,
        hypothetical_price=input_.hypothetical_price,
        price_change_fraction=(input_.hypothetical_price / input_.base_price)
        - Decimal("1"),
        assumptions=input_.assumptions,
        blocked_conclusions=(
            "No forecast, recommendation, entry price, stop, target, size or "
            "notification can be derived from synthetic data.",
            "Fresh observed quote, primary evidence and approved deterministic "
            "valuation/risk policy remain required.",
        ),
    )
