from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from nomy_trader.counterfactual import ScenarioInput, run_scenario


def scenario(**changes: object) -> ScenarioInput:
    values: dict[str, object] = {
        "id": "brze-12",
        "symbol": "BRZE",
        "as_of": datetime(2026, 9, 9, tzinfo=UTC),
        "base_observation_id": "ajaib:BRZE",
        "base_price": Decimal("24.68"),
        "hypothetical_price": Decimal("12"),
        "assumptions": ("Educational scenario.",),
    }
    values.update(changes)
    return ScenarioInput(**values)


def test_scenario_is_explicitly_synthetic_and_non_actionable() -> None:
    result = run_scenario(scenario())

    assert result.status == "SCENARIO_ONLY"
    assert result.price_change_fraction == Decimal("12") / Decimal("24.68") - 1
    assert "recommendation" in result.blocked_conclusions[0].lower()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_price", Decimal("0")),
        ("hypothetical_price", Decimal("-1")),
        ("as_of", datetime(2026, 9, 9)),
        ("base_price", Decimal("12")),
    ],
)
def test_scenario_rejects_invalid_or_non_counterfactual_inputs(
    field: str, value: object
) -> None:
    changes = {field: value}
    if field == "base_price" and value == Decimal("12"):
        changes["hypothetical_price"] = Decimal("12")
    with pytest.raises((ValidationError, ValueError)):
        scenario(**changes)
