"""Shared bullish signal classification for analysis passes."""

from __future__ import annotations

BULLISH_SIGNALS = frozenset({"buy", "overweight"})


def is_bullish_signal(signal: str | None) -> bool:
    if signal is None:
        return False
    return signal.strip().lower() in BULLISH_SIGNALS
