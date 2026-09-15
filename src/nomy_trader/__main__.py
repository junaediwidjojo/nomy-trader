"""Run a bounded discovery/recheck cycle with local credentials."""

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from dotenv import load_dotenv
from pydantic import ValidationError

from nomy_trader.analysis.compare import compare_profiles, print_compare_table
from nomy_trader.analysis.pipeline import format_price, run_analyze_pipeline
from nomy_trader.counterfactual import ScenarioInput, run_scenario
from nomy_trader.market.ajaib_catalog import import_user_catalog
from nomy_trader.market.ajaib_hints import run_reversal_hint_scan
from nomy_trader.market.daily_recheck import recheck_daily
from nomy_trader.providers.ajaib_us_stock import (
    AjaibUsStockAuthError,
    AjaibUsStockError,
    fetch_us_stock_catalog_to_file,
)
from nomy_trader.providers.fmp import FmpError
from nomy_trader.providers.massive import MassiveClient, MassiveError
from nomy_trader.providers.sec_edgar import SecEdgarClient, SecEdgarError
from nomy_trader.providers.twelve_data import TwelveDataClient, TwelveDataError
from nomy_trader.signals import PriceSignalFixture, run_price_signal_fixture
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.rate_limit import RateLimited, reserve_credits, reserve_request
from nomy_trader.storage.schema import scan_runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recheck a logged FMP candidate using daily bars"
    )
    parser.add_argument(
        "command",
        choices=[
            "recheck",
            "twelve-quote",
            "ajaib-import",
            "ajaib-fetch",
            "ajaib-hints",
            "sec-filings",
            "counterfactual",
            "price-signal",
            "analyze",
            "run",
            "compare-profiles",
        ],
    )
    parser.add_argument(
        "--symbol", help="Default: first candidate in the latest saved FMP scan"
    )
    parser.add_argument(
        "--scenario-input",
        type=Path,
        default=Path("examples/brze_12_scenario.json"),
        help="Explicit synthetic JSON input for counterfactual",
    )
    parser.add_argument(
        "--price-signal-input",
        type=Path,
        default=Path("examples/price_signal_fixture.json"),
        help="Explicit offline JSON input for price-signal",
    )
    parser.add_argument("--database", type=Path, default=Path("var/nomy-trader.sqlite"))
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("config/private_ajaib_us_stock.json"),
        help="Complete manually supplied Ajaib JSON response for ajaib-import",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=12,
        help="Number of ranked Ajaib hints to print or analyze (default: 12)",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Explicit symbols for analyze; skips top-N hint selection",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Per-symbol TradingAgents timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("var/screen_analyze_results.json"),
        help="JSON output path for analyze",
    )
    parser.add_argument(
        "--skip-catalog-import",
        action="store_true",
        help="Use the latest SQLite catalog instead of importing --input",
    )
    parser.add_argument(
        "--force-reanalyze",
        action="store_true",
        help="Ignore TradingAgents cache and rerun live analysis",
    )
    parser.add_argument(
        "--fetch-catalog",
        action="store_true",
        help="Fetch Ajaib US-stock JSON via session cookie before import/run",
    )
    parser.add_argument(
        "--skip-confirm",
        action="store_true",
        help="Stay on the baseline model; run no high-model confirmation pass",
    )
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)
    key = os.getenv("MASSIVE_API_KEY", "")
    twelve_key = os.getenv("TWELVE_DATA_API_KEY", "")
    sec_user_agent = os.getenv("SEC_USER_AGENT", "")
    if args.command == "recheck" and not key:
        print("MASSIVE_API_KEY is missing from environment or local .env")
        return 1
    if args.command == "twelve-quote" and not twelve_key:
        print("TWELVE_DATA_API_KEY is missing from environment or local .env")
        return 1
    if args.command == "compare-profiles" and not args.symbol:
        print("Supply --symbol for profile comparison")
        return 1
    if args.command == "sec-filings" and not sec_user_agent:
        print("SEC_USER_AGENT is missing from environment or local .env")
        return 1
    if args.command == "counterfactual":
        try:
            scenario = ScenarioInput.model_validate_json(
                args.scenario_input.read_text(encoding="utf-8")
            )
            scenario_result = run_scenario(scenario)
        except (OSError, ValidationError, ValueError) as exc:
            print(f"Scenario stopped: {exc}")
            return 1
        print(
            f"{scenario_result.status} {scenario_result.symbol} "
            f"hypothetical ${scenario_result.hypothetical_price}"
        )
        print(
            f"Base observation: ${scenario_result.base_price} "
            f"({scenario_result.base_observation_id})"
        )
        percentage_change = scenario_result.price_change_fraction * 100
        print(f"Synthetic price change: {percentage_change:.2f}%")
        print("Assumptions:")
        for assumption in scenario_result.assumptions:
            print(f"- {assumption}")
        print("Blocked conclusions:")
        for conclusion in scenario_result.blocked_conclusions:
            print(f"- {conclusion}")
        return 0
    if args.command == "price-signal":
        try:
            fixture = PriceSignalFixture.model_validate_json(
                args.price_signal_input.read_text(encoding="utf-8")
            )
            price_signal_result = run_price_signal_fixture(fixture)
        except (OSError, ValidationError, ValueError) as exc:
            print(f"Price signal stopped: {exc}")
            return 1
        print(
            json.dumps(
                price_signal_result.model_dump(mode="json"), indent=2, sort_keys=True
            )
        )
        return 0
    if args.command == "ajaib-fetch":
        try:
            count = fetch_us_stock_catalog_to_file(args.input)
        except (AjaibUsStockAuthError, AjaibUsStockError, OSError) as exc:
            print(f"Ajaib fetch stopped: {exc}")
            return 1
        print(f"AJAIB_FETCHED {count} entries -> {args.input}")
        return 0
    args.database.parent.mkdir(parents=True, exist_ok=True)
    if args.database.exists():
        # SQLite backup safely includes committed WAL data before schema upgrade.
        backup = args.database.with_name(args.database.name + ".before-massive-backup")
        if not backup.exists():
            with (
                sqlite3.connect(args.database) as source,
                sqlite3.connect(backup) as target,
            ):
                source.backup(target)
    engine = open_database(args.database)
    try:
        upgrade(engine)
        if args.command == "compare-profiles":
            profiles = ("two_round_debate", "high_model_one_round")

            def _compare_progress(
                index: int, total: int, profile: str, symbol: str
            ) -> None:
                print(
                    f"COMPARE {index}/{total} {symbol} profile={profile}...",
                    flush=True,
                )

            try:
                compare_run = compare_profiles(
                    args.symbol,
                    profiles,
                    timeout_seconds=max(args.timeout, 420),
                    on_progress=_compare_progress,
                )
            except (OSError, ValueError, FileNotFoundError) as exc:
                print(f"Compare stopped: {exc}")
                return 1
            print_compare_table(compare_run)
            print(f"Saved {compare_run.output_path}")
            print(compare_run.limitation)
            return 0
        if args.command in {"analyze", "run"}:
            if args.fetch_catalog:
                try:
                    count = fetch_us_stock_catalog_to_file(args.input)
                except (AjaibUsStockAuthError, AjaibUsStockError, OSError) as exc:
                    print(f"Ajaib fetch stopped: {exc}")
                    return 1
                print(f"AJAIB_FETCHED {count} entries -> {args.input}", flush=True)
            import_path = None if args.skip_catalog_import else args.input
            if import_path is not None and not import_path.exists():
                print(f"Ajaib input missing: {import_path}")
                return 1

            def _progress(index: int, total: int, symbol: str, mode: str) -> None:
                labels = {
                    "primary": "TRADINGAGENTS",
                    "confirm": "CONFIRM-BUY",
                }
                print(
                    f"{labels.get(mode, mode)} {index}/{total} {symbol}...",
                    flush=True,
                )

            try:
                if import_path is not None:
                    print(f"IMPORTING {import_path}", flush=True)
                analyze_run = run_analyze_pipeline(
                    engine,
                    now=datetime.now(UTC),
                    top=args.top,
                    symbols=tuple(args.symbols) if args.symbols else None,
                    import_path=import_path,
                    output_path=args.output,
                    timeout_seconds=args.timeout,
                    on_progress=_progress,
                    force_refresh=args.force_reanalyze,
                    confirm_bullish=not args.skip_confirm,
                )
            except (OSError, ValueError, FileNotFoundError, FmpError) as exc:
                print(f"Run stopped: {exc}")
                return 1
            if analyze_run.catalog_imported:
                print(
                    f"CATALOGUE_IMPORTED {analyze_run.catalog_entry_count} entries",
                    flush=True,
                )
            print(
                f"SCREENED {analyze_run.candidates_screened} decline candidates",
                flush=True,
            )
            print(
                f"FMP_PRESCREEN checked={analyze_run.fmp_checked} "
                f"passed={len(analyze_run.fmp_passed)} "
                f"rejected={len(analyze_run.fmp_rejected)} "
                f"reused={sum(1 for r in analyze_run.fmp_rows if r.source == 'cache')}",
                flush=True,
            )
            for row in analyze_run.fmp_rows:
                if row.passed:
                    metrics = row.metrics
                    extra = ""
                    if metrics is not None:
                        extra = (
                            f" close=${metrics.close} "
                            f"1d {metrics.one_day_percent}%"
                        )
                    print(f"FMP_PASS {row.symbol}{extra}", flush=True)
                else:
                    print(
                        f"FMP_REJECT {row.symbol} {','.join(row.reasons)}",
                        flush=True,
                    )
            print(
                f"ANALYZE_COMPLETE {analyze_run.symbols_analyzed} symbols | "
                f"{analyze_run.catalogue_revision} | "
                f"cache_hits={analyze_run.cache_hits} "
                f"live_runs={analyze_run.cache_misses} "
                f"buy_confirmations={analyze_run.buy_confirmations_run} "
                f"(ttl={analyze_run.cache_ttl_hours}h)"
            )
            print(
                f"{'Rank':<5} {'Symbol':<8} {'Signal':<12} {'Confirm':<12} "
                f"{'Src':<6} {'Ajaib':<10} {'Target':<10} {'Up%':<8} {'Entry hint'}"
            )
            for item in analyze_run.results:
                screened = item.screened
                rank = str(screened.rank) if screened is not None else "-"
                ajaib = format_price(screened.ajaib_price if screened else None)
                target = format_price(item.price_target)
                source = item.source or "-"
                confirm = "-"
                if item.confirmatory is not None:
                    confirm = item.confirmatory.signal or item.confirmatory.error or "-"
                    if len(str(confirm)) > 12:
                        confirm = str(confirm)[:9] + "..."
                entry = item.entry_hint or item.executive_summary or item.error or "-"
                if len(entry) > 56:
                    entry = entry[:53] + "..."
                upside = (
                    f"{item.target_upside * 100:+.1f}%"
                    if item.target_upside is not None
                    else "-"
                )
                print(
                    f"{rank:<5} {item.symbol:<8} {(item.signal or '-'):<12} "
                    f"{str(confirm):<12} {source:<6} {ajaib:<10} {target:<10} "
                    f"{upside:<8} {entry}"
                )
            print(f"Saved {analyze_run.output_path}")
            print(
                f"BUY_SCAN screened={analyze_run.candidates_screened} "
                f"analyzed_top={analyze_run.analyze_top} "
                f"primary_bullish={len(analyze_run.primary_bullish)} "
                f"upside={len(analyze_run.upside_candidates)} "
                f"confirmed={len(analyze_run.confirmed_bullish)} "
                f"disputed={len(analyze_run.disputed_bullish)}"
            )
            if analyze_run.primary_bullish:
                print("PRIMARY_BULLISH " + ", ".join(analyze_run.primary_bullish))
            if analyze_run.upside_candidates:
                print("UPSIDE_CANDIDATES " + ", ".join(analyze_run.upside_candidates))
            if analyze_run.confirmed_bullish:
                print("CONFIRMED_BULLISH " + ", ".join(analyze_run.confirmed_bullish))
            if analyze_run.disputed_bullish:
                print("DISPUTED_BULLISH " + ", ".join(analyze_run.disputed_bullish))
            if analyze_run.buy_candidates_path:
                print(f"Buy detail: {analyze_run.buy_candidates_path}")
            print(analyze_run.limitation)
            return 0
        if args.command == "ajaib-import":
            snapshot = import_user_catalog(engine, args.input, datetime.now(UTC))
            print(
                f"CATALOGUE_IMPORTED {snapshot.catalog_entry_count} source entries | "
                f"{len(snapshot.symbols)} working symbols | {snapshot.revision}"
            )
            return 0
        if args.command == "ajaib-hints":
            if args.top < 1:
                print("--top must be positive")
                return 1
            scan = run_reversal_hint_scan(engine, datetime.now(UTC))
            print(
                f"RESEARCH_HINTS {len(scan.candidates)} of {scan.source_entries} "
                f"from {scan.catalogue_revision}"
            )
            policy = scan.priority_policy
            print(
                "PRIORITY_POLICY "
                f"{policy.version} | one-day x{policy.one_day_weight} | "
                f"one-week x{policy.one_week_weight} | "
                f"one-month x{policy.one_month_weight} above "
                f"{policy.one_month_floor}%, capped at "
                f"{policy.one_month_context_cap_fraction}x weekly+daily severity"
            )
            for ranked in scan.ranked_candidates[: args.top]:
                candidate = ranked.hint
                month = (
                    str(candidate.one_month_percent)
                    if candidate.one_month_percent is not None
                    else "unavailable"
                )
                print(
                    f"#{ranked.rank} {candidate.symbol} | "
                    f"score {ranked.breakdown.total} "
                    f"(day {ranked.breakdown.one_day_severity}, "
                    f"week {ranked.breakdown.one_week_severity}, "
                    f"month {ranked.breakdown.one_month_reversal_context}) | "
                    f"${candidate.price} | "
                    f"1d {candidate.one_day_percent}% | "
                    f"1w {candidate.one_week_percent}% | "
                    f"1m {month}%"
                )
            if len(scan.ranked_candidates) > args.top:
                print(
                    f"Showing {args.top} of {len(scan.ranked_candidates)} "
                    "ranked hints; "
                    "the full ranking is saved in SQLite."
                )
            print(scan.limitation)
            return 0
        if args.command == "sec-filings":
            if args.symbol is None:
                print("Supply --symbol for SEC filing lookup")
                return 1
            with SecEdgarClient(sec_user_agent) as client:
                filings = client.latest_filings(args.symbol, {"8-K", "10-K", "10-Q"})
            print(
                f"SEC_FILINGS {args.symbol.upper()} | {len(filings)} metadata records"
            )
            for filing in filings:
                print(
                    f"{filing.form} | {filing.filed_at.date()} | {filing.document_url}"
                )
            print("Filing metadata only; no analysis, plan, or notification.")
            return 0
        symbol = args.symbol
        if symbol is None:
            with engine.connect() as conn:
                rows = conn.execute(
                    sa.select(scan_runs.c.payload).order_by(
                        scan_runs.c.started_at.desc()
                    )
                )
                for row in rows:
                    payload = json.loads(row[0])
                    if payload.get("kind") == "fmp_biggest_losers" and payload.get(
                        "candidates"
                    ):
                        symbol = payload["candidates"][0]["symbol"]
                        break
        if symbol is None:
            print("No saved FMP candidates. Supply --symbol or run discovery first.")
            return 1
        if args.command == "twelve-quote":
            with TwelveDataClient(
                twelve_key,
                lambda credits: reserve_credits(
                    engine, "twelve_data", datetime.now(UTC), credits
                ),
            ) as client:
                quote = client.quote(symbol)
            print(
                f"DATA_OBSERVED {symbol} | source timestamp {quote.as_of.isoformat()}"
            )
            print(f"Close: ${quote.close} | previous close: ${quote.previous_close}")
            print(f"Volume: {quote.volume}")
            print(
                "Limited-venue reference only; no eligibility, plan, or notification."
            )
            return 0
        with MassiveClient(
            key, lambda: reserve_request(engine, "massive", datetime.now(UTC))
        ) as client:
            result = recheck_daily(engine, client, symbol, datetime.now(UTC))
        latest, previous = result.bars.results[-1], result.bars.results[-2]
        change = (latest.c / previous.c - 1) * 100
        print(f"DATA_RECHECKED {symbol} | session {latest.session_date}")
        print(f"Close: ${latest.c} | daily change: {change:.2f}% | volume: {latest.v}")
        print(f"Saved {len(result.bars.results)} daily bars to {args.database}")
        print(result.limitation)
        return 0
    except (
        MassiveError,
        SecEdgarError,
        TwelveDataError,
        RateLimited,
        ValueError,
    ) as exc:
        print(f"Recheck stopped: {exc}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
