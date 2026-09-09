from datetime import UTC, datetime
from decimal import Decimal

from nomy_trader.market.fresh_market import confirmation_from_twelve_quote
from nomy_trader.providers.twelve_data import Quote
from nomy_trader.signals import MarketCondition


def test_maps_twelve_quote_without_inventing_market_conditions() -> None:
    quote = Quote(
        symbol="BRZE",
        timestamp=int(datetime(2026, 9, 9, 10, tzinfo=UTC).timestamp()),
        close=Decimal("24.52"),
        previous_close=Decimal("26.18"),
        volume=Decimal("5797306"),
    )

    confirmation = confirmation_from_twelve_quote(
        quote,
        checked_at=datetime(2026, 9, 9, 10, 1, tzinfo=UTC),
        maximum_age_seconds=120,
        conditions=(
            MarketCondition(name="configured_volume_check", passed=True, detail="met"),
        ),
        venue_limitation="Quote availability is provider-defined.",
    )

    assert confirmation.provider == "Twelve Data"
    assert confirmation.reference_price == Decimal("24.52")
    assert confirmation.conditions[0].name == "configured_volume_check"
