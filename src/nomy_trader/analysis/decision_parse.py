"""Legacy import path; structured JSON is the only accepted decision contract."""

from nomy_trader.analysis.structured_decision import (
    AnalystDecision,
    DecisionRejected,
    accept_analyst_decision,
)

__all__ = ["AnalystDecision", "DecisionRejected", "accept_analyst_decision"]
