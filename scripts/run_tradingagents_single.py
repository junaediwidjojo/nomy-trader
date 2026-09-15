#!/usr/bin/env python3
"""Run TradingAgents for one symbol; emit one JSON object on stdout."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

NOMY_ROOT = Path(__file__).resolve().parents[1]
NOMY_SRC = NOMY_ROOT / "src"


def _load_nomy_env() -> None:
    env = NOMY_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _complete_structured_decision(
    final_decision: str, model: str
) -> tuple[str | None, str | None]:
    """Ask the same backend for the nomy-trader JSON contract. Do not repair fields."""
    sys.path.insert(0, str(NOMY_SRC))
    from nomy_trader.analysis.structured_decision import (
        STRUCTURED_DECISION_SYSTEM,
        analyst_decision_json_schema,
    )

    api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY") or os.environ.get(
        "OPENAI_API_KEY"
    )
    base_url = os.environ.get("TRADINGAGENTS_LLM_BACKEND_URL")
    if not api_key:
        return None, "missing API key for structured decision"
    try:
        from openai import OpenAI
    except ImportError:
        return None, "openai package missing in TradingAgents venv"
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    messages = [
        {"role": "system", "content": STRUCTURED_DECISION_SYSTEM},
        {
            "role": "user",
            "content": (
                "Emit the JSON contract for this analysis. Absolute prices only. "
                "If quotes are missing, rating must be REVIEW.\n\n"
                f"{final_decision}"
            ),
        },
    ]
    schema = analyst_decision_json_schema()
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "analyst_decision",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
    except Exception:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            return None, f"structured decision completion failed: {exc}"
    content = completion.choices[0].message.content
    if not content or not str(content).strip():
        return None, "structured decision completion returned empty content"
    return str(content), None


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
    final_decision = str(final_state.get("final_trade_decision") or "")
    model = str(config.get("quick_think_llm") or config.get("deep_think_llm") or "")
    structured, structured_error = _complete_structured_decision(final_decision, model)
    payload = {
        "ticker": ticker,
        "signal": signal,
        "report_path": str(report_path),
        "final_decision": final_decision,
        "structured_decision": structured,
        "structured_decision_error": structured_error,
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
