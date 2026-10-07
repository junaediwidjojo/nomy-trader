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
    """Entry and stop are required advisory levels, not orders or size.

    Target is optional: TradingAgents often omits **Price Target** while still
    stating Overweight plus entry/stop. Those names stay useful.
    """

    rating: AnalystRating
    entry: Positive
    stop: Positive
    target: Positive | None = None
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
            "target": {"type": ["number", "null"]},
            "horizon": {"type": "string", "minLength": 1},
            "why": {"type": "string", "minLength": 1},
        },
    }


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


def _scalar_rating(value: object) -> object:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def decision_from_tradingagents(
    portfolio: dict[str, Any] | None,
    trader: dict[str, Any] | None,
) -> dict[str, Any]:
    """Map TradingAgents typed agent output onto the nomy-trader contract.

    No extra LLM call. Fail closed when the graph fell back to markdown or
    omitted entry/stop.
    """
    if not portfolio:
        raise DecisionRejected(
            "Portfolio Manager returned no structured object (markdown fallback)"
        )
    if not trader:
        raise DecisionRejected(
            "Trader returned no structured object (markdown fallback)"
        )
    why = portfolio.get("executive_summary") or portfolio.get("investment_thesis")
    horizon = portfolio.get("time_horizon")
    if not isinstance(why, str) or not why.strip():
        raise DecisionRejected("Portfolio Manager omitted rationale")
    if not isinstance(horizon, str) or not horizon.strip():
        raise DecisionRejected("Portfolio Manager omitted time_horizon")
    return {
        "rating": _scalar_rating(portfolio.get("rating")),
        "entry": trader.get("entry_price"),
        "stop": trader.get("stop_loss"),
        "target": portfolio.get("price_target"),
        "horizon": horizon.strip(),
        "why": why.strip(),
    }


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
