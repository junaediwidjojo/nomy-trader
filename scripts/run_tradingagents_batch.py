#!/usr/bin/env python3
"""Run bounded TradingAgents analysis for shortlisted symbols."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

# Load nomy-trader .env before importing TradingAgents
_env = Path(__file__).resolve().parents[1] / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            import os

            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "TradingAgents"))

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402


def run_symbol(ticker: str, trade_date: str) -> dict:
    config = DEFAULT_CONFIG.copy()
    config["results_dir"] = str(
        Path.home() / ".tradingagents" / "logs" / "nomy-trader-session"
    )
    ta = TradingAgentsGraph(
        selected_analysts=("market", "fundamentals"),
        debug=False,
        config=config,
    )
    final_state, signal = ta.propagate(ticker, trade_date)
    report_path = ta.save_reports(final_state, ticker)
    return {
        "ticker": ticker,
        "signal": signal,
        "report_path": str(report_path),
        "market_report_len": len(final_state.get("market_report") or ""),
        "fundamentals_report_len": len(final_state.get("fundamentals_report") or ""),
        "market_preview": (final_state.get("market_report") or "")[:200],
        "fundamentals_preview": (final_state.get("fundamentals_report") or "")[:200],
        "final_decision": final_state.get("final_trade_decision", ""),
    }


def main() -> None:
    tickers = sys.argv[1:] or ["BRZE"]
    trade_date = date.today().isoformat()
    results = []
    for ticker in tickers:
        print(f"Running {ticker}...", flush=True)
        try:
            result = run_symbol(ticker, trade_date)
            results.append(result)
            print(
                f"  signal={result['signal']} "
                f"market={result['market_report_len']}b "
                f"fundamentals={result['fundamentals_report_len']}b",
                flush=True,
            )
        except Exception as exc:
            results.append({"ticker": ticker, "error": str(exc)})
            print(f"  ERROR: {exc}", flush=True)
    out = (
        Path(__file__).resolve().parents[1]
        / "var"
        / "tradingagents_batch_results.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"Results written to {out}")


if __name__ == "__main__":
    main()
