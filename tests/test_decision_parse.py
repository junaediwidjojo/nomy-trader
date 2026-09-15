import json
from decimal import Decimal

import pytest

from nomy_trader.analysis.structured_decision import (
    AnalystRating,
    DecisionRejected,
    accept_analyst_decision,
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


def test_empty_quotes_fail_closed() -> None:
    payload = dict(VALID)
    payload["target"] = None
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
