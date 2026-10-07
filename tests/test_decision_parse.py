import json
from decimal import Decimal

import pytest

from nomy_trader.analysis.structured_decision import (
    AnalystRating,
    DecisionRejected,
    accept_analyst_decision,
    decision_from_tradingagents,
)

VALID = {
    "rating": "Hold",
    "entry": "31.59",
    "stop": "28.0",
    "target": "34.0",
    "horizon": "6-12 months",
    "why": "Wait for a rebound above the 10-day EMA.",
}

MARKDOWN = """**Rating**: Hold

**Executive Summary**: Maintain exposure; add only if price rebounds above
the 10-day EMA ($31.59).

**Price Target**: 34.0

**Time Horizon**: 6-12 months"""


def test_map_tradingagents_typed_agents() -> None:
    mapped = decision_from_tradingagents(
        {
            "rating": "Overweight",
            "executive_summary": "Add a modest hedged position.",
            "investment_thesis": "Trend intact.",
            "price_target": None,
            "time_horizon": "6-12 months",
        },
        {
            "action": "Buy",
            "entry_price": 381.5,
            "stop_loss": 373.5,
        },
    )
    decision = accept_analyst_decision({"structured_decision": mapped})
    assert decision.rating is AnalystRating.OVERWEIGHT
    assert decision.entry == Decimal("381.5")
    assert decision.stop == Decimal("373.5")
    assert decision.target is None


def test_map_fails_when_agents_fell_back_to_markdown() -> None:
    with pytest.raises(DecisionRejected, match="Portfolio Manager"):
        decision_from_tradingagents(None, {"entry_price": 1, "stop_loss": 1})
    with pytest.raises(DecisionRejected, match="Trader"):
        decision_from_tradingagents(
            {
                "rating": "Hold",
                "executive_summary": "Wait.",
                "time_horizon": "6 months",
            },
            None,
        )


def test_map_fails_when_trader_omits_stop() -> None:
    mapped = decision_from_tradingagents(
        {
            "rating": "Overweight",
            "executive_summary": "Add.",
            "time_horizon": "6-12 months",
        },
        {"action": "Buy", "entry_price": 381.5, "stop_loss": None},
    )
    with pytest.raises(DecisionRejected, match="schema"):
        accept_analyst_decision({"structured_decision": mapped})


def test_accept_structured_object() -> None:
    decision = accept_analyst_decision({"ticker": "FIZZ", "structured_decision": VALID})
    assert decision.rating is AnalystRating.HOLD
    assert decision.entry == Decimal("31.59")
    assert decision.target == Decimal("34.0")
    assert decision.stop == Decimal("28.0")


def test_accept_json_string() -> None:
    decision = accept_analyst_decision({"structured_decision": json.dumps(VALID)})
    assert decision.rating is AnalystRating.HOLD


def test_review_fails_closed() -> None:
    payload = dict(VALID)
    payload["rating"] = "REVIEW"
    with pytest.raises(DecisionRejected, match="REVIEW"):
        accept_analyst_decision({"structured_decision": payload})


def test_overweight_survives_without_target() -> None:
    payload = {
        "rating": "Overweight",
        "entry": "381.5",
        "stop": "373.5",
        "target": None,
        "horizon": "6-12 months",
        "why": "Long-term trend intact; limited hedged add.",
    }
    decision = accept_analyst_decision({"structured_decision": payload})
    assert decision.rating is AnalystRating.OVERWEIGHT
    assert decision.target is None
    omitted = {key: value for key, value in payload.items() if key != "target"}
    decision = accept_analyst_decision({"structured_decision": omitted})
    assert decision.rating is AnalystRating.OVERWEIGHT


def test_empty_quotes_fail_closed() -> None:
    payload = dict(VALID)
    payload["entry"] = None
    with pytest.raises(DecisionRejected, match="schema"):
        accept_analyst_decision({"structured_decision": payload})
    omitted = {key: value for key, value in VALID.items() if key != "stop"}
    with pytest.raises(DecisionRejected, match="schema"):
        accept_analyst_decision({"structured_decision": omitted})


def test_markdown_only_fails_closed() -> None:
    with pytest.raises(DecisionRejected, match="not valid JSON"):
        accept_analyst_decision({"final_decision": MARKDOWN, "signal": "Hold"})


def test_graph_signal_is_not_used_as_repair() -> None:
    with pytest.raises(DecisionRejected):
        accept_analyst_decision({"signal": "Buy", "final_decision": MARKDOWN})


def test_malformed_json_fails_closed() -> None:
    with pytest.raises(DecisionRejected, match="not valid JSON"):
        accept_analyst_decision({"structured_decision": '{"rating": "Hold",}'})
