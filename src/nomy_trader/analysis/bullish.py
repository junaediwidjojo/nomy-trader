"""Shared bullish signal classification for analysis passes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

BULLISH_SIGNALS = frozenset({"buy", "overweight"})
BEARISH_SIGNALS = frozenset({"sell", "underweight", "reduce"})

# The baseline profile almost never emits Buy, so a Hold whose own price target
# sits above the live price also counts as a candidate. Widened from 10% after a
# 10% floor surfaced only three names across 274 screened candidates.
MIN_UPSIDE_FRACTION = Decimal("0.05")


def is_bullish_signal(signal: str | None) -> bool:
    if signal is None:
        return False
    return signal.strip().lower() in BULLISH_SIGNALS


def is_bearish_signal(signal: str | None) -> bool:
    if signal is None:
        return False
    return signal.strip().lower() in BEARISH_SIGNALS


def upside_fraction(
    price_target: str | Decimal | None,
    reference_price: Decimal | None,
) -> Decimal | None:
    """Fractional gap from the live price to the model's own target."""
    if price_target is None or reference_price is None or reference_price <= 0:
        return None
    try:
        target = Decimal(str(price_target).replace("$", "").replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    if target <= 0:
        return None
    return target / reference_price - 1


def qualifies_on_upside(
    signal: str | None,
    price_target: str | Decimal | None,
    reference_price: Decimal | None,
) -> bool:
    """A non-bearish rating carrying at least the minimum target upside."""
    if is_bearish_signal(signal):
        return False
    fraction = upside_fraction(price_target, reference_price)
    return fraction is not None and fraction >= MIN_UPSIDE_FRACTION
