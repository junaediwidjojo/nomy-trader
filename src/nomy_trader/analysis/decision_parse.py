"""Parse supplementary fields from TradingAgents final_trade_decision text."""

from __future__ import annotations

import re

_RATING = re.compile(r"\*\*Rating\*\*:\s*([A-Za-z]+)")
_PRICE_TARGET = re.compile(r"\*\*Price Target\*\*:\s*\$?([\d,.]+)")
_TIME_HORIZON = re.compile(r"\*\*Time Horizon\*\*:\s*(.+?)(?:\n\n|\Z)", re.DOTALL)
_EXEC_SUMMARY = re.compile(
    r"\*\*Executive Summary\*\*:\s*(.+?)(?:\n\n\*\*|\Z)",
    re.DOTALL,
)
_ENTRY_HINT = re.compile(
    r"(?:entry|add(?:ing)?|buy(?:ing)?|rebound(?:s)? above|above the)"
    r"\s[^.\n]{0,120}\$[\d,.]+",
    re.IGNORECASE,
)


def parse_rating(text: str) -> str | None:
    match = _RATING.search(text)
    return match.group(1) if match else None


def parse_price_target(text: str) -> str | None:
    match = _PRICE_TARGET.search(text)
    if match is None:
        return None
    return match.group(1).replace(",", "")


def parse_time_horizon(text: str) -> str | None:
    match = _TIME_HORIZON.search(text)
    if match is None:
        return None
    return " ".join(match.group(1).split())


def parse_executive_summary(text: str) -> str | None:
    match = _EXEC_SUMMARY.search(text)
    if match is None:
        return None
    return " ".join(match.group(1).split())


def parse_entry_hint(text: str) -> str | None:
    match = _ENTRY_HINT.search(text)
    if match is None:
        return None
    return " ".join(match.group(0).split())


def parse_final_decision(text: str) -> dict[str, str | None]:
    """Extract advisory fields from a TradingAgents final decision block."""
    return {
        "rating": parse_rating(text),
        "price_target": parse_price_target(text),
        "time_horizon": parse_time_horizon(text),
        "executive_summary": parse_executive_summary(text),
        "entry_hint": parse_entry_hint(text),
    }
