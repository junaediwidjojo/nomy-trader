"""Ajaib screen → TradingAgents review pipeline for the simplified MVP."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import Field
from sqlalchemy import Engine

from nomy_trader.analysis.bullish import is_bullish_signal
from nomy_trader.analysis.buy_scan import (
    summarize_buy_candidates,
    write_buy_scan_summary,
)
from nomy_trader.analysis.cache import (
    TradingAgentsCacheEntry,
    cache_ttl,
    load_fresh_cache_entry,
    profile_cache_key,
    save_cache_entry,
)
from nomy_trader.analysis.decision_parse import parse_final_decision
from nomy_trader.analysis.profiles import (
    CONFIRM_BUY_PROFILE,
    DEFAULT_RUN_PROFILE,
    confirm_buy_env_overrides,
    default_run_env_overrides,
)
from nomy_trader.domain.models import Contract, Finite, Positive, Text, Timestamp
from nomy_trader.market.ajaib_catalog import import_user_catalog
from nomy_trader.market.ajaib_hints import AjaibReversalHintScan, run_reversal_hint_scan


class ScreenedSymbol(Contract):
    symbol: Text
    issuer_name: Text
    ajaib_price: Positive
    one_day_percent: Finite
    one_week_percent: Finite
    rank: int = Field(gt=0)


class SymbolAnalysis(Contract):
    symbol: Text
    screened: ScreenedSymbol | None = None
    signal: Text | None = None
    rating: Text | None = None
    price_target: Text | None = None
    entry_hint: Text | None = None
    time_horizon: Text | None = None
    executive_summary: Text | None = None
    report_path: Text | None = None
    error: Text | None = None
    source: Text | None = None
    analyzed_at: Timestamp | None = None
    confirmatory: SymbolAnalysis | None = None
    confirmatory_profile: Text | None = None


class AnalyzeRun(Contract):
    observed_at: Timestamp
    catalogue_revision: Text | None = None
    catalog_imported: bool = False
    catalog_entry_count: int | None = None
    candidates_screened: int = Field(ge=0)
    analyze_top: int = Field(gt=0)
    symbols_analyzed: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)
    cache_ttl_hours: int = Field(gt=0)
    buy_confirmations_run: int = Field(ge=0)
    primary_bullish: tuple[Text, ...] = ()
    confirmed_bullish: tuple[Text, ...] = ()
    disputed_bullish: tuple[Text, ...] = ()
    buy_candidates_path: Text | None = None
    results: tuple[SymbolAnalysis, ...]
    output_path: Text
    limitation: Text


def default_tradingagents_python(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[3]
    configured = os.getenv("TRADINGAGENTS_PYTHON")
    if configured:
        return Path(configured)
    return root.parent / "TradingAgents" / ".venv" / "bin" / "python"


def tradingagents_timeout_seconds() -> int:
    raw = os.getenv("TRADINGAGENTS_RUNNER_TIMEOUT_SECONDS", "300")
    return int(raw)


def run_tradingagents_subprocess(
    symbol: str,
    *,
    project_root: Path | None = None,
    timeout_seconds: int | None = None,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    root = project_root or Path(__file__).resolve().parents[3]
    python = default_tradingagents_python(root)
    script = root / "scripts" / "run_tradingagents_single.py"
    if not python.exists():
        raise FileNotFoundError(
            f"TradingAgents python not found at {python}; set TRADINGAGENTS_PYTHON"
        )
    if not script.exists():
        raise FileNotFoundError(f"runner script not found at {script}")
    child_env = os.environ.copy()
    if env_overrides:
        child_env.update(env_overrides)
    completed = subprocess.run(
        [str(python), str(script), symbol.upper()],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout_seconds or tradingagents_timeout_seconds(),
        check=False,
        env=child_env,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(detail)
    payload: dict[str, object] = json.loads(completed.stdout)
    return payload


def analyze_symbol(
    raw: dict[str, object],
    screened: ScreenedSymbol | None,
) -> SymbolAnalysis:
    final_decision = str(raw.get("final_decision") or "")
    parsed = parse_final_decision(final_decision)
    return SymbolAnalysis(
        symbol=str(raw["ticker"]),
        screened=screened,
        signal=str(raw.get("signal") or parsed["rating"] or "UNAVAILABLE"),
        rating=parsed["rating"],
        price_target=parsed["price_target"],
        entry_hint=parsed["entry_hint"],
        time_horizon=parsed["time_horizon"],
        executive_summary=parsed["executive_summary"],
        report_path=str(raw["report_path"]) if raw.get("report_path") else None,
    )


def confirmatory_timeout_seconds() -> int:
    raw = os.getenv("TRADINGAGENTS_CONFIRM_TIMEOUT_SECONDS", "900")
    return int(raw)


def _run_symbol_analysis(
    symbol: str,
    screened: ScreenedSymbol | None,
    *,
    env_overrides: dict[str, str],
    profile_key: str,
    project_root: Path,
    timeout_seconds: int,
    clock: datetime,
    force_refresh: bool,
) -> SymbolAnalysis:
    if not force_refresh:
        cached = load_fresh_cache_entry(
            symbol,
            profile_key,
            now=clock,
            project_root=project_root,
        )
        if cached is not None:
            analysis = analyze_symbol(cached.runner_payload, screened)
            return analysis.model_copy(
                update={"source": "cache", "analyzed_at": cached.analyzed_at}
            )
    raw = run_tradingagents_subprocess(
        symbol,
        project_root=project_root,
        timeout_seconds=timeout_seconds,
        env_overrides=env_overrides,
    )
    analysis = analyze_symbol(raw, screened).model_copy(
        update={"source": "live", "analyzed_at": clock}
    )
    save_cache_entry(
        TradingAgentsCacheEntry(
            symbol=symbol.upper(),
            profile_key=profile_key,
            analyzed_at=clock,
            runner_payload=raw,
        ),
        project_root=project_root,
    )
    return analysis


def analyze_symbols(
    symbols: tuple[str, ...],
    scan: AjaibReversalHintScan | None = None,
    *,
    project_root: Path | None = None,
    timeout_seconds: int | None = None,
    on_progress: Callable[[int, int, str, str], None] | None = None,
    now: datetime | None = None,
    force_refresh: bool = False,
    confirm_bullish: bool = True,
) -> tuple[SymbolAnalysis, ...]:
    screened_by_symbol: dict[str, ScreenedSymbol] = {}
    if scan is not None:
        for ranked in scan.ranked_candidates:
            hint = ranked.hint
            screened_by_symbol[hint.symbol] = ScreenedSymbol(
                symbol=hint.symbol,
                issuer_name=hint.issuer_name,
                ajaib_price=hint.price,
                one_day_percent=hint.one_day_percent,
                one_week_percent=hint.one_week_percent,
                rank=ranked.rank,
            )
    clock = (now or datetime.now(UTC)).astimezone(UTC)
    root = project_root or Path(__file__).resolve().parents[3]
    primary_env = default_run_env_overrides()
    primary_key = profile_cache_key(primary_env)
    confirm_env = confirm_buy_env_overrides()
    confirm_key = profile_cache_key(confirm_env)
    primary_timeout = timeout_seconds or tradingagents_timeout_seconds()
    results: list[SymbolAnalysis] = []
    total = len(symbols)
    for index, symbol in enumerate(symbols, start=1):
        screened = screened_by_symbol.get(symbol.upper())
        if on_progress is not None:
            on_progress(index, total, symbol.upper(), "primary")
        try:
            analysis = _run_symbol_analysis(
                symbol,
                screened,
                env_overrides=primary_env,
                profile_key=primary_key,
                project_root=root,
                timeout_seconds=primary_timeout,
                clock=clock,
                force_refresh=force_refresh,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
            RuntimeError,
            json.JSONDecodeError,
        ) as exc:
            analysis = SymbolAnalysis(
                symbol=symbol.upper(),
                screened=screened,
                error=str(exc),
                source="live",
                analyzed_at=clock,
            )
        if confirm_bullish and is_bullish_signal(analysis.signal):
            if on_progress is not None:
                on_progress(index, total, symbol.upper(), "confirm")
            try:
                confirmed = _run_symbol_analysis(
                    symbol,
                    screened,
                    env_overrides=confirm_env,
                    profile_key=confirm_key,
                    project_root=root,
                    timeout_seconds=confirmatory_timeout_seconds(),
                    clock=clock,
                    force_refresh=force_refresh,
                )
                analysis = analysis.model_copy(
                    update={
                        "confirmatory": confirmed,
                        "confirmatory_profile": CONFIRM_BUY_PROFILE,
                    }
                )
            except (
                OSError,
                subprocess.TimeoutExpired,
                RuntimeError,
                json.JSONDecodeError,
            ) as exc:
                analysis = analysis.model_copy(
                    update={
                        "confirmatory": SymbolAnalysis(
                            symbol=symbol.upper(),
                            screened=screened,
                            error=str(exc),
                            source="live",
                            analyzed_at=clock,
                        ),
                        "confirmatory_profile": CONFIRM_BUY_PROFILE,
                    }
                )
        results.append(analysis)
    return tuple(results)


def run_analyze_pipeline(
    engine: Engine,
    *,
    now: datetime,
    top: int,
    symbols: tuple[str, ...] | None = None,
    import_path: Path | None = None,
    project_root: Path | None = None,
    output_path: Path | None = None,
    timeout_seconds: int | None = None,
    on_progress: Callable[[int, int, str, str], None] | None = None,
    force_refresh: bool = False,
) -> AnalyzeRun:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("analyze clock must be timezone-aware")
    now = now.astimezone(UTC)
    root = project_root or Path(__file__).resolve().parents[3]
    catalog_imported = False
    catalog_entry_count: int | None = None
    if import_path is not None:
        snapshot = import_user_catalog(engine, import_path, now)
        catalog_imported = True
        catalog_entry_count = snapshot.catalog_entry_count
    scan = run_reversal_hint_scan(engine, now)
    if symbols:
        selected = tuple(symbol.upper() for symbol in symbols)
    else:
        if top < 1:
            raise ValueError("--top must be positive")
        selected = tuple(
            ranked.hint.symbol for ranked in scan.ranked_candidates[:top]
        )
    if not selected:
        raise ValueError(
            "no screened candidates; import a fresh Ajaib snapshot or relax filters"
        )
    results = analyze_symbols(
        selected,
        scan,
        project_root=root,
        timeout_seconds=timeout_seconds,
        on_progress=on_progress,
        now=now,
        force_refresh=force_refresh,
    )
    cache_hits = sum(1 for item in results if item.source == "cache")
    cache_misses = sum(1 for item in results if item.source == "live")
    buy_confirmations = sum(
        1 for item in results if item.confirmatory is not None
    )
    ttl_hours = int(cache_ttl().total_seconds() // 3600)
    buy_summary = summarize_buy_candidates(
        results,
        observed_at=now,
        catalogue_revision=scan.catalogue_revision,
        candidates_screened=len(scan.candidates),
    )
    buy_path = write_buy_scan_summary(buy_summary, project_root=root)
    out = output_path or (root / "var" / "screen_analyze_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    analyzed_top = len(selected)
    run = AnalyzeRun(
        observed_at=now,
        catalogue_revision=scan.catalogue_revision,
        catalog_imported=catalog_imported,
        catalog_entry_count=catalog_entry_count,
        candidates_screened=len(scan.candidates),
        analyze_top=analyzed_top,
        symbols_analyzed=len(results),
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        cache_ttl_hours=ttl_hours,
        buy_confirmations_run=buy_confirmations,
        primary_bullish=buy_summary.primary_bullish,
        confirmed_bullish=buy_summary.confirmed_bullish,
        disputed_bullish=buy_summary.disputed_bullish,
        buy_candidates_path=str(buy_path),
        results=results,
        output_path=str(out),
        limitation=(
            "Supplementary TradingAgents sandbox output only; not execution, "
            "position sizing, or a profitability claim. Primary screening uses "
            "one debate round on gpt-oss-120b; Buy/Overweight triggers a "
            "high_model_two_round_debate confirmation pass."
        ),
    )
    out.write_text(json.dumps(run.model_dump(mode="json"), indent=2), encoding="utf-8")
    stamp = root / "var" / "latest_run_stamp.txt"
    stamp.write_text(
        "\n".join(
            [
                f"observed_at={now.isoformat()}",
                f"catalogue_revision={scan.catalogue_revision}",
                f"candidates_screened={len(scan.candidates)}",
                f"symbols_analyzed={len(results)}",
                f"profile={DEFAULT_RUN_PROFILE}",
                f"model={default_run_env_overrides()['TRADINGAGENTS_DEEP_THINK_LLM']}",
                f"debate_rounds={default_run_env_overrides()['TRADINGAGENTS_MAX_DEBATE_ROUNDS']}",
                f"output={out}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return run


def format_price(value: Decimal | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, Decimal):
        return f"${value:.2f}"
    return f"${value}" if not str(value).startswith("$") else str(value)
