"""Compare TradingAgents profiles on the same symbol."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from nomy_trader.analysis.pipeline import (
    SymbolAnalysis,
    analyze_symbol,
    format_price,
    run_tradingagents_subprocess,
)
from nomy_trader.analysis.profiles import TRADINGAGENTS_PROFILES
from nomy_trader.domain.models import Contract, Text, Timestamp


class ProfileComparison(Contract):
    profile: Text
    description: Text
    config: dict[str, object]
    analysis: SymbolAnalysis


class CompareRun(Contract):
    observed_at: Timestamp
    symbol: Text
    comparisons: tuple[ProfileComparison, ...]
    output_path: Text
    limitation: Text


def compare_profiles(
    symbol: str,
    profile_names: tuple[str, ...],
    *,
    project_root: Path | None = None,
    timeout_seconds: int | None = None,
    on_progress: Callable[[int, int, str, str], None] | None = None,
) -> CompareRun:
    root = project_root or Path(__file__).resolve().parents[3]
    now = datetime.now(UTC)
    comparisons: list[ProfileComparison] = []
    total = len(profile_names)
    for index, profile_name in enumerate(profile_names, start=1):
        profile = TRADINGAGENTS_PROFILES.get(profile_name)
        if profile is None:
            raise ValueError(f"unknown profile: {profile_name}")
        if on_progress is not None:
            on_progress(index, total, profile_name, symbol.upper())
        try:
            raw = run_tradingagents_subprocess(
                symbol,
                project_root=root,
                timeout_seconds=timeout_seconds,
                env_overrides=profile.env_overrides,
            )
            analysis = analyze_symbol(raw, screened=None)
            config = {
                "max_debate_rounds": raw.get("max_debate_rounds"),
                "max_risk_discuss_rounds": raw.get("max_risk_discuss_rounds"),
                "deep_think_llm": raw.get("deep_think_llm"),
                "quick_think_llm": raw.get("quick_think_llm"),
                "elapsed_seconds": raw.get("elapsed_seconds"),
            }
        except Exception as exc:
            analysis = SymbolAnalysis(symbol=symbol.upper(), error=str(exc))
            config = dict(profile.env_overrides)
        comparisons.append(
            ProfileComparison(
                profile=profile.name,
                description=profile.description,
                config=config,
                analysis=analysis,
            )
        )
    out = root / "var" / "tradingagents_profile_compare.json"
    run = CompareRun(
        observed_at=now,
        symbol=symbol.upper(),
        comparisons=tuple(comparisons),
        output_path=str(out),
        limitation=(
            "Profile comparison uses supplementary TradingAgents sandbox output "
            "only; not execution advice or a profitability claim."
        ),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run.model_dump(mode="json"), indent=2), encoding="utf-8")
    return run


def print_compare_table(run: CompareRun) -> None:
    print(f"PROFILE_COMPARE {run.symbol}")
    for item in run.comparisons:
        analysis = item.analysis
        elapsed = item.config.get("elapsed_seconds", "-")
        model = item.config.get("deep_think_llm") or item.config.get(
            "TRADINGAGENTS_DEEP_THINK_LLM", "-"
        )
        debates = item.config.get("max_debate_rounds") or item.config.get(
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS", "-"
        )
        print(
            f"\n[{item.profile}] {item.description}\n"
            f"  model={model} | debate_rounds={debates} | elapsed={elapsed}s"
        )
        if analysis.error:
            error = analysis.error
            if len(error) > 240:
                error = error[:237] + "..."
            print(f"  ERROR: {error}")
            continue
        print(
            f"  signal={analysis.signal} | target={format_price(analysis.price_target)}"
        )
        summary = analysis.executive_summary or analysis.entry_hint or "-"
        if len(summary) > 220:
            summary = summary[:217] + "..."
        print(f"  summary: {summary}")
