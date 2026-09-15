"""Strict JSON contract for supplementary TradingAgents decisions.

Fail closed: no regex repair of markdown ratings, no coercing empty quotes.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from nomy_trader.domain.models import Contract, Positive, Text


class AnalystRating(StrEnum):
    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"
    REVIEW = "REVIEW"


class AnalystDecision(Contract):
    """Required quotes are advisory levels, not orders or position size."""

    rating: AnalystRating
    entry: Positive
    stop: Positive
    target: Positive
    horizon: Text
    why: Text


class DecisionRejected(ValueError):
    """Model output did not satisfy the owned contract."""


_FENCE_PREFIX = "```"


def analyst_decision_json_schema() -> dict[str, Any]:
    """JSON Schema for OpenAI-compatible `response_format.json_schema`."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["rating", "entry", "stop", "target", "horizon", "why"],
        "properties": {
            "rating": {
                "type": "string",
                "enum": [item.value for item in AnalystRating],
            },
            "entry": {"type": "number"},
            "stop": {"type": "number"},
            "target": {"type": "number"},
            "horizon": {"type": "string", "minLength": 1},
            "why": {"type": "string", "minLength": 1},
        },
    }


STRUCTURED_DECISION_SYSTEM = (
    "Reply with a single JSON object only. Keys: rating, entry, stop, target, "
    "horizon, why. rating must be exactly one of Buy, Overweight, Hold, "
    "Underweight, Sell, or REVIEW. entry, stop, and target must be absolute "
    "prices as JSON numbers (not percents, not ranges, not null). horizon is "
    "the holding window. why is a short rationale. If you cannot name all "
    "three prices from the analysis, set rating to REVIEW anyway — the "
    "consumer will reject REVIEW. Do not wrap the object in markdown."
)


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith(_FENCE_PREFIX):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith(_FENCE_PREFIX):
        lines = lines[1:]
    if lines and lines[-1].strip() == _FENCE_PREFIX:
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_json_object(text: str) -> dict[str, Any]:
    """Load JSON object from a whole string. Do not scan prose for fields."""
    candidate = _strip_markdown_fence(text)
    try:
        loaded: object = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise DecisionRejected("structured decision is not valid JSON") from exc
    if not isinstance(loaded, dict):
        raise DecisionRejected("structured decision must be a JSON object")
    return loaded


def accept_analyst_decision(payload: dict[str, Any]) -> AnalystDecision:
    """Validate runner JSON. Markdown-only or REVIEW fails closed."""
    raw: object
    if "structured_decision" in payload:
        raw = payload["structured_decision"]
        if raw is None:
            detail = payload.get("structured_decision_error")
            if isinstance(detail, str) and detail.strip():
                raise DecisionRejected(detail)
            raise DecisionRejected("missing structured_decision")
        if isinstance(raw, str):
            data = parse_json_object(raw)
        elif isinstance(raw, dict):
            data = raw
        else:
            raise DecisionRejected(
                "structured_decision must be an object or JSON string"
            )
    else:
        final_decision = payload.get("final_decision")
        if not isinstance(final_decision, str) or not final_decision.strip():
            raise DecisionRejected("missing structured_decision")
        data = parse_json_object(final_decision)
    try:
        decision = AnalystDecision.model_validate(data)
    except ValidationError as exc:
        raise DecisionRejected("structured decision failed schema validation") from exc
    if decision.rating is AnalystRating.REVIEW:
        raise DecisionRejected("rating REVIEW is fail-closed")
    return decision
