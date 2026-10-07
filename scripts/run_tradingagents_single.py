#!/usr/bin/env python3
"""Run TradingAgents for one symbol; emit one JSON object on stdout."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

NOMY_ROOT = Path(__file__).resolve().parents[1]
NOMY_SRC = NOMY_ROOT / "src"

_STRUCTURED_CONSUMERS = (
    "tradingagents.agents.utils.structured",
    "tradingagents.agents.managers.portfolio_manager",
    "tradingagents.agents.managers.research_manager",
    "tradingagents.agents.trader.trader",
    "tradingagents.agents.analysts.sentiment_analyst",
)


def _load_nomy_env() -> None:
    env = NOMY_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _install_structured_capture(
    captured: dict[str, Any], errors: dict[str, str]
) -> None:
    """Rebind invoke_structured_or_freetext on every agent module.

    Agents bind the function at import time (``from ... import invoke``), so
    patching only ``structured.py`` is not enough after those imports.
    """

    def invoke_structured_or_freetext(
        structured_llm: Any,
        plain_llm: Any,
        prompt: Any,
        render: Any,
        agent_name: str,
    ) -> str:
        if structured_llm is not None:
            try:
                result = structured_llm.invoke(prompt)
                if result is None:
                    raise ValueError("structured output returned no parsed result")
                captured[agent_name] = result.model_dump(mode="json")
                return render(result)
            except Exception as exc:
                errors[agent_name] = f"{type(exc).__name__}: {exc}"
                print(
                    f"{agent_name} structured output failed ({type(exc).__name__})",
                    file=sys.stderr,
                )
        captured.setdefault(agent_name, None)
        response = plain_llm.invoke(prompt)
        return response.content

    for module_name in _STRUCTURED_CONSUMERS:
        module = sys.modules.get(module_name)
        if module is not None:
            module.invoke_structured_or_freetext = invoke_structured_or_freetext


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_tradingagents_single.py TICKER", file=sys.stderr)
        return 2
    ticker = sys.argv[1].upper()
    _load_nomy_env()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "TradingAgents"))
    sys.path.insert(0, str(NOMY_SRC))

    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    from nomy_trader.analysis.structured_decision import (
        DecisionRejected,
        decision_from_tradingagents,
    )

    captured: dict[str, Any] = {}
    capture_errors: dict[str, str] = {}

    config = DEFAULT_CONFIG.copy()
    config["results_dir"] = str(
        Path.home() / ".tradingagents" / "logs" / "nomy-trader-session"
    )
    graph = TradingAgentsGraph(
        selected_analysts=("market", "fundamentals"),
        debug=False,
        config=config,
    )
    _install_structured_capture(captured, capture_errors)
    started = time.monotonic()
    final_state, signal = graph.propagate(ticker, date.today().isoformat())
    elapsed_seconds = round(time.monotonic() - started, 1)
    report_path = graph.save_reports(final_state, ticker)
    final_decision = str(final_state.get("final_trade_decision") or "")
    structured: dict[str, Any] | None = None
    structured_error: str | None = None
    try:
        structured = decision_from_tradingagents(
            captured.get("Portfolio Manager"),
            captured.get("Trader"),
        )
    except DecisionRejected as exc:
        structured_error = str(exc)
    payload = {
        "ticker": ticker,
        "signal": signal,
        "report_path": str(report_path),
        "final_decision": final_decision,
        "structured_decision": structured,
        "structured_decision_error": structured_error,
        "structured_source": "tradingagents_structured",
        "tradingagents_structured": {
            "portfolio_manager": captured.get("Portfolio Manager"),
            "trader": captured.get("Trader"),
            "research_manager": captured.get("Research Manager"),
        },
        "tradingagents_structured_errors": capture_errors,
        "market_report_len": len(final_state.get("market_report") or ""),
        "fundamentals_report_len": len(final_state.get("fundamentals_report") or ""),
        "elapsed_seconds": elapsed_seconds,
        "max_debate_rounds": config.get("max_debate_rounds"),
        "max_risk_discuss_rounds": config.get("max_risk_discuss_rounds"),
        "deep_think_llm": config.get("deep_think_llm"),
        "quick_think_llm": config.get("quick_think_llm"),
    }
    sys.stdout.write(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
