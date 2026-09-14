from nomy_trader.analysis.decision_parse import parse_final_decision

SAMPLE = """**Rating**: Hold

**Executive Summary**: Maintain exposure; add only if price rebounds above
the 10-day EMA ($31.59).

**Investment Thesis**: Mixed signals.

**Price Target**: 34.0

**Time Horizon**: 6-12 months"""


def test_parse_final_decision_extracts_advisory_fields() -> None:
    parsed = parse_final_decision(SAMPLE)
    assert parsed["rating"] == "Hold"
    assert parsed["price_target"] == "34.0"
    assert parsed["time_horizon"] == "6-12 months"
    assert parsed["executive_summary"] is not None
    assert "$31.59" in (parsed["entry_hint"] or "")
