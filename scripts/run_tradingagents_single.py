#!/usr/bin/env python3
"""Run TradingAgents for one symbol; emit one JSON object on stdout."""

from __future__ import annotations

import inspect
import json
import math
import os
import sys
import time
from datetime import date
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zoneinfo import ZoneInfo

NOMY_ROOT = Path(__file__).resolve().parents[1]
NOMY_SRC = NOMY_ROOT / "src"

_STRUCTURED_CONSUMERS = (
    "tradingagents.agents.utils.structured",
    "tradingagents.agents.managers.portfolio_manager",
    "tradingagents.agents.managers.research_manager",
    "tradingagents.agents.trader.trader",
    "tradingagents.agents.analysts.sentiment_analyst",
)


def _install_financial_currency_context(graph: Any, observed: dict[str, Any]) -> None:
    """Label financial evidence before analysts can mix statement/quote units."""
    import yfinance as yf
    from tradingagents.dataflows.stockstats_utils import yf_with_timeout

    names = {
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
    }
    seen: set[int] = set()

    def wrap_tool(func: Any) -> Any:
        signature = inspect.signature(func)

        @wraps(func)
        def labeled(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(*args, **kwargs)
            symbol = str(bound.arguments["ticker"]).upper()
            result = func(*args, **kwargs)
            if not isinstance(result, str) or result.startswith("Error"):
                return result
            if symbol not in observed:
                info = yf_with_timeout(lambda: yf.Ticker(symbol).info, 20)
                financial = info.get("financialCurrency")
                quote = info.get("currency")
                if not financial or not quote:
                    raise ValueError(
                        f"Financial/quote currency unavailable for {symbol}"
                    )
                observed[symbol] = {
                    "financial_currency": financial,
                    "quote_currency": quote,
                    "source": "Yahoo Finance Ticker.info",
                }
            context = observed[symbol]
            return (
                f"# Provider currency metadata for {symbol}\n"
                f"Financial statement currency: {context['financial_currency']}\n"
                f"Share-price / market-cap currency: {context['quote_currency']}\n"
                "Statement amounts are raw units unless explicitly labeled.\n"
                "Revenue, profit, cash, debt and cash flows use financial currency.\n"
                "Preserve reported currency; convert only with a sourced FX rate.\n"
                "Do not combine amounts denominated in different currencies.\n"
                "Do not infer ordinary-share/ADS equivalence "
                "or per-share EPS currency.\n"
                "Calculate year-over-year growth from matching periods; "
                "do not infer it from a sequential change.\n\n" + result
            )

        return labeled

    for node in graph.tool_nodes.values():
        for tool in node.tools_by_name.values():
            if tool.name in names and id(tool) not in seen:
                seen.add(id(tool))
                tool.func = wrap_tool(tool.func)


def _pin_tool_dates(graph: Any, analysis_date: str, overrides: list[Any]) -> None:
    """Keep tool as-of dates aligned with this runner's current-date analysis."""
    seen: set[int] = set()

    def wrap_tool(func: Any, name: str) -> Any:
        signature = inspect.signature(func)
        dates = {"curr_date", "end_date"} & signature.parameters.keys()

        @wraps(func)
        def pinned(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(*args, **kwargs)
            for key in dates:
                requested = bound.arguments.get(key)
                if requested != analysis_date:
                    overrides.append(
                        {
                            "tool": name,
                            "field": key,
                            "requested": requested,
                            "used": analysis_date,
                        }
                    )
                bound.arguments[key] = analysis_date
            return func(*bound.args, **bound.kwargs)

        return pinned

    for node in graph.tool_nodes.values():
        for tool in node.tools_by_name.values():
            if id(tool) not in seen and callable(getattr(tool, "func", None)):
                seen.add(id(tool))
                tool.func = wrap_tool(tool.func, tool.name)


def _pin_tool_symbols(graph: Any, ticker: str, overrides: list[Any]) -> None:
    """Scope this single-instrument runner's provider requests and audit overrides."""
    seen: set[int] = set()

    def wrap_tool(func: Any, name: str) -> Any:
        signature = inspect.signature(func)
        symbols = {"ticker", "symbol"} & signature.parameters.keys()

        @wraps(func)
        def scoped(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(*args, **kwargs)
            for field in symbols:
                requested = bound.arguments.get(field)
                if requested != ticker:
                    overrides.append(
                        {
                            "tool": name,
                            "field": field,
                            "requested": requested,
                            "used": ticker,
                        }
                    )
                bound.arguments[field] = ticker
            return func(*bound.args, **bound.kwargs)

        return scoped

    for node in graph.tool_nodes.values():
        for tool in node.tools_by_name.values():
            if id(tool) not in seen and callable(getattr(tool, "func", None)):
                seen.add(id(tool))
                tool.func = wrap_tool(tool.func, tool.name)


def _install_financial_analyst(context: dict[str, Any]) -> None:
    """Replace free-form financial-table generation with reproducible evidence."""
    setup = sys.modules["tradingagents.graph.setup"]

    def factory(llm: Any) -> Any:
        def node(state: Any) -> Any:
            from langchain_core.messages import AIMessage
            from tradingagents.dataflows.stockstats_utils import yf_with_timeout

            from nomy_trader.analysis.financial_evidence import (
                FinancialEvidenceRequest,
                financial_evidence,
                render_financial_evidence,
            )

            tools = context["graph"].tool_nodes["fundamentals"].tools_by_name
            kwargs = {"ticker": context["ticker"], "curr_date": state["trade_date"]}
            profile = yf_with_timeout(
                lambda: tools["get_fundamentals"].func(**kwargs), 30
            )
            # Per-share currency and ADS/ordinary-share equivalence are unverified.
            profile = "\n".join(
                line
                for line in profile.splitlines()
                if not line.startswith(("EPS (TTM):", "Forward EPS:", "Book Value:"))
            )
            statements = {}
            for name in ("income_statement", "balance_sheet", "cashflow"):
                tool = tools[f"get_{name}"]
                statements[name] = yf_with_timeout(
                    lambda tool=tool: tool.func(**kwargs, freq="quarterly"), 30
                )
            currency = context["currencies"][context["ticker"]]
            evidence = financial_evidence(
                FinancialEvidenceRequest(
                    symbol=context["ticker"],
                    as_of=state["trade_date"],
                    financial_currency=currency["financial_currency"],
                    quote_currency=currency["quote_currency"],
                    statements=statements,
                )
            )
            context["evidence"] = evidence
            context["sources"] = statements
            report = render_financial_evidence(evidence)
            report += "\n\n# Provider current profile (not issuer-verified)\n" + profile
            return {
                "fundamentals_report": report,
                "messages": [AIMessage(content=report)],
            }

        return node

    setup.create_fundamentals_analyst = factory


def _restore_reported_close(recent: Any, metadata: dict[str, Any]) -> Any:
    """Use a timestamped closing-session quote only for its matching daily row."""
    import pandas as pd

    stamp = metadata.get("regularMarketTime")
    if stamp is None:
        return recent
    when = (
        pd.Timestamp(stamp, unit="s", tz="UTC")
        if isinstance(stamp, (int, float))
        else pd.Timestamp(stamp)
    )
    if when.tzinfo is None:
        return recent
    when = when.tz_convert("America/New_York")
    if when.hour < 16:
        return recent
    try:
        price = float(metadata["regularMarketPrice"])
    except (KeyError, TypeError, ValueError):
        return recent
    if not math.isfinite(price) or price <= 0:
        return recent
    day = pd.Timestamp(when.date())
    missing = (recent["Date"] == day) & recent["Close"].isna()
    # A quoted close outside the reported daily range is inconsistent evidence.
    matching = missing & recent["Low"].le(price) & recent["High"].ge(price)
    restored = recent.copy()
    restored.loc[matching, "Close"] = price
    return restored


def _merge_recent_ohlcv(frame: Any, recent: Any, curr_date: str) -> Any:
    import pandas as pd

    cutoff = pd.Timestamp(curr_date).normalize()
    recent = recent[
        (recent["Date"] <= cutoff) & recent["Close"].notna() & recent["Close"].gt(0)
    ]
    if recent.empty:
        raise ValueError("Recent Yahoo history has no usable closing prices")
    # Preserve adjusted historical rows; append only missing recent sessions.
    recent = recent[recent["Date"] > frame["Date"].max()]
    return (
        pd.concat([frame, recent], ignore_index=True)
        .drop_duplicates("Date", keep="last")
        .sort_values("Date")
        .reset_index(drop=True)
    )


def _install_recent_ohlcv_refresh(refreshed: dict[str, Any]) -> None:
    """Supplement long downloads with fresh recent bars before indicators."""
    import pandas as pd
    from tradingagents.dataflows import stockstats_utils as stats

    original = stats.load_ohlcv
    frames: dict[tuple[str, str], Any] = {}

    def load_ohlcv(symbol: str, curr_date: str) -> Any:
        key = (symbol, curr_date)
        if key not in frames:
            frame = original(symbol, curr_date)
            canonical = stats.normalize_symbol(symbol)
            ticker = stats.yf.Ticker(canonical)
            recent = stats.yf_with_timeout(
                lambda: ticker.history(period="5d", auto_adjust=False),
                20,
            )
            if recent.empty:
                raise ValueError(f"Recent Yahoo history unavailable for {symbol}")
            recent = stats._clean_dataframe(recent.reset_index())
            metadata = stats.yf_with_timeout(lambda: ticker.history_metadata, 20)
            recent = _restore_reported_close(recent, metadata)
            today_ny = pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize()
            completed = recent[
                (recent["Date"] < today_ny.tz_localize(None))
                & (recent["Date"] <= pd.Timestamp(curr_date))
            ]
            if not completed.empty and completed["Close"].isna().iloc[-1]:
                raise ValueError(f"Latest completed Yahoo bar is unpriced: {symbol}")
            merged = _merge_recent_ohlcv(frame, recent, curr_date)
            refreshed[f"{symbol}@{curr_date}"] = {
                "original_latest_date": str(frame["Date"].iloc[-1].date()),
                "latest_date": str(merged["Date"].iloc[-1].date()),
                "latest_close": float(merged["Close"].iloc[-1]),
                "source": "Yahoo recent history, fetched during this run",
                "regular_market_time": str(metadata.get("regularMarketTime")),
                "regular_market_price": metadata.get("regularMarketPrice"),
            }
            frames[key] = merged
        return frames[key].copy()

    # Several tool modules bind load_ohlcv at import time.
    for name, module in list(sys.modules.items()):
        if name.startswith("tradingagents.") and (
            getattr(module, "load_ohlcv", None) is original
        ):
            module.load_ohlcv = load_ohlcv


def _install_evidence_guard() -> None:
    """Stop before debate when either selected analyst produced no report."""
    setup = sys.modules["tradingagents.graph.setup"]
    factory = setup.create_bull_researcher

    def guarded_factory(llm: Any) -> Any:
        node = factory(llm)

        def guarded_node(state: Any) -> Any:
            missing = [
                key
                for key in ("market_report", "fundamentals_report")
                if not str(state.get(key) or "").strip()
            ]
            if missing:
                raise ValueError("Analysis evidence missing: " + ", ".join(missing))
            return node(state)

        return guarded_node

    setup.create_bull_researcher = guarded_factory


class _JsonSchemaInvoker:
    """Include schema instructions as well as provider-side constraints."""

    def __init__(self, llm: Any, schema: Any, max_tokens: int | None = None) -> None:
        if max_tokens is not None:
            if max_tokens < 1:
                raise ValueError("Decision token budget must be positive")
            # Clone only this decision client; do not inflate every debate call.
            llm = llm.model_copy(update={"max_tokens": max_tokens})
        self.bound = llm.with_structured_output(
            schema, method="json_schema", strict=True
        )
        self.financial_context: dict[str, Any] | None = None
        self.instructions = (
            "Return one JSON object matching this schema. Include every required "
            "field, including investment_thesis when requested. Use null only "
            "where allowed; do not invent missing evidence or price levels.\n"
            "For Trader: if no new trade is proposed, set entry_price and "
            "stop_loss to null; a trim/exit price is not a new long entry. "
            "For Portfolio Manager: include a nonempty time_horizon reflecting "
            "the proposed holding/reassessment condition. "
            "Financial calculations are in the deterministic financial report; "
            "do not invent new financial figures, fiscal labels or FX conversions. "
            "Other agents' claims are unverified, not additional evidence.\n"
            + json.dumps(schema.model_json_schema())
        )

    def invoke(self, prompt: Any) -> Any:
        instructions = self.instructions
        if self.financial_context and self.financial_context.get("evidence"):
            instructions += (
                "\nCanonical provider financial evidence follows. It takes precedence "
                "over conflicting numerical claims in the debate; issuer agreement "
                "is unverified. Do not assume holdings, portfolio weights or user "
                "risk budgets.\n" + json.dumps(self.financial_context["evidence"])
            )
        if isinstance(prompt, str):
            prompt = prompt + "\n\n" + instructions
        else:
            messages = (
                prompt.to_messages() if hasattr(prompt, "to_messages") else prompt
            )
            prompt = [*messages, {"role": "user", "content": instructions}]
        return self.bound.invoke(prompt)


def _install_structured_binding(
    financial_context: dict[str, Any] | None = None,
) -> None:
    """Override agent-local bindings before graph construction, not after it.

    Higher-model manager calls opt into native schema enforcement.
    Other agents keep their provider's existing tool-calling dispatch.
    """
    method = os.getenv("TRADINGAGENTS_STRUCTURED_METHOD", "auto")
    if method == "auto":
        return
    if method != "json_schema":
        raise ValueError(f"unsupported structured method: {method}")

    def portfolio_binding(default_bind: Any) -> Any:
        def bind_structured(llm: Any, schema: Any, agent_name: str) -> Any:
            budget_keys = {
                "Portfolio Manager": "TRADINGAGENTS_PORTFOLIO_MAX_TOKENS",
                "Research Manager": "TRADINGAGENTS_RESEARCH_MAX_TOKENS",
                "Trader": "TRADINGAGENTS_TRADER_MAX_TOKENS",
            }
            if agent_name not in budget_keys:
                return default_bind(llm, schema, agent_name)
            if agent_name == "Portfolio Manager":
                from pydantic import Field, create_model

                schema = create_model(
                    "RequiredPortfolioDecision",
                    __base__=schema,
                    time_horizon=(str, Field(min_length=1, pattern=r"\S")),
                )
            # Surface binding failures rather than silently disable enforcement.
            budget = int(os.getenv(budget_keys[agent_name], "8192"))
            bound = _JsonSchemaInvoker(llm, schema, max_tokens=budget)
            bound.financial_context = financial_context
            return bound

        return bind_structured

    for module_name in _STRUCTURED_CONSUMERS:
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "bind_structured"):
            module.bind_structured = portfolio_binding(module.bind_structured)


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


def _decision_from_captured(captured: dict[str, Any]) -> dict[str, Any]:
    from nomy_trader.analysis.structured_decision import (
        DecisionRejected,
        decision_from_tradingagents,
    )

    if (
        os.getenv("TRADINGAGENTS_STRUCTURED_METHOD") == "json_schema"
        and captured.get("Research Manager") is None
    ):
        raise DecisionRejected("Research Manager structured review unavailable")
    return decision_from_tradingagents(
        captured.get("Portfolio Manager"), captured.get("Trader")
    )


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

    from nomy_trader.analysis.structured_decision import DecisionRejected

    captured: dict[str, Any] = {}
    capture_errors: dict[str, str] = {}
    refreshed_ohlcv: dict[str, Any] = {}
    tool_date_overrides: list[Any] = []
    financial_currency_context: dict[str, Any] = {}
    tool_symbol_overrides: list[Any] = []
    financial_context: dict[str, Any] = {
        "ticker": ticker,
        "currencies": financial_currency_context,
    }

    config = DEFAULT_CONFIG.copy()
    # A separate, empty directory bypasses existing provider files without
    # deleting historical evidence. Keep it alive until graph execution ends.
    fresh_cache = None
    if os.getenv("NOMY_FORCE_FRESH_DATA") == "1":
        fresh_cache = TemporaryDirectory(prefix="nomy-fresh-data-")
        config["data_cache_dir"] = fresh_cache.name
        _install_recent_ohlcv_refresh(refreshed_ohlcv)
    config["results_dir"] = str(
        Path.home() / ".tradingagents" / "logs" / "nomy-trader-session"
    )
    _install_structured_binding(financial_context)
    _install_evidence_guard()
    _install_financial_analyst(financial_context)
    graph = TradingAgentsGraph(
        selected_analysts=("market", "fundamentals"),
        debug=False,
        config=config,
    )
    _install_financial_currency_context(graph, financial_currency_context)
    _pin_tool_symbols(graph, ticker, tool_symbol_overrides)
    financial_context["graph"] = graph
    if os.getenv("NOMY_FORCE_FRESH_DATA") == "1":
        _pin_tool_dates(graph, date.today().isoformat(), tool_date_overrides)
    _install_structured_capture(captured, capture_errors)
    started = time.monotonic()
    final_state, signal = graph.propagate(ticker, date.today().isoformat())
    if fresh_cache is not None:
        fresh_cache.cleanup()
    elapsed_seconds = round(time.monotonic() - started, 1)
    report_path = graph.save_reports(final_state, ticker)
    final_decision = str(final_state.get("final_trade_decision") or "")
    structured: dict[str, Any] | None = None
    structured_error: str | None = None
    try:
        structured = _decision_from_captured(captured)
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
        "structured_method": os.getenv("TRADINGAGENTS_STRUCTURED_METHOD", "auto"),
        "structured_method_scope": "Research Manager, Portfolio Manager, Trader",
        "portfolio_max_tokens": os.getenv("TRADINGAGENTS_PORTFOLIO_MAX_TOKENS"),
        "research_max_tokens": os.getenv("TRADINGAGENTS_RESEARCH_MAX_TOKENS"),
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
        "fresh_data_requested": os.getenv("NOMY_FORCE_FRESH_DATA") == "1",
        "recent_ohlcv_refresh": refreshed_ohlcv,
        "tool_date_overrides": tool_date_overrides,
        "financial_currency_context": financial_currency_context,
        "tool_symbol_overrides": tool_symbol_overrides,
        "financial_evidence": financial_context.get("evidence"),
        "financial_source_documents": financial_context.get("sources"),
        "financial_report_source": "deterministic_provider_cells",
        "model_commentary_issuer_verified": False,
    }
    sys.stdout.write(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
