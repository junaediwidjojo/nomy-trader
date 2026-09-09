"""Adapters that turn provider observations into explicit market-gate facts."""

from datetime import datetime

from nomy_trader.providers.twelve_data import Quote
from nomy_trader.signals import MarketCondition, MarketConfirmation


def confirmation_from_twelve_quote(
    quote: Quote,
    *,
    checked_at: datetime,
    maximum_age_seconds: int,
    conditions: tuple[MarketCondition, ...],
    venue_limitation: str,
) -> MarketConfirmation:
    """Map a quote without inventing liquidity or technical-condition results."""
    return MarketConfirmation(
        symbol=quote.symbol,
        provider="Twelve Data",
        venue_limitation=venue_limitation,
        quote_as_of=quote.as_of,
        checked_at=checked_at,
        reference_price=quote.close,
        maximum_age_seconds=maximum_age_seconds,
        conditions=conditions,
    )
