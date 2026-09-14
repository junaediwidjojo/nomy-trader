#!/usr/bin/env python3
"""Run TradingAgents for one symbol; emit one JSON object on stdout."""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path


def _load_nomy_env() -> None:
    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return
    import os

    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_tradingagents_single.py TICKER", file=sys.stderr)
        return 2
    ticker = sys.argv[1].upper()
    _load_nomy_env()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "TradingAgents"))

    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = DEFAULT_CONFIG.copy()
    config["results_dir"] = str(
        Path.home() / ".tradingagents" / "logs" / "nomy-trader-session"
    )
    graph = TradingAgentsGraph(
        selected_analysts=("market", "fundamentals"),
        debug=False,
        config=config,
    )
    started = time.monotonic()
    final_state, signal = graph.propagate(ticker, date.today().isoformat())
    elapsed_seconds = round(time.monotonic() - started, 1)
    report_path = graph.save_reports(final_state, ticker)
    payload = {
        "ticker": ticker,
        "signal": signal,
        "report_path": str(report_path),
        "final_decision": final_state.get("final_trade_decision", ""),
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
