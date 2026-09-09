"""Run a bounded discovery/recheck cycle with local credentials."""

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from dotenv import load_dotenv

from nomy_trader.market.ajaib_catalog import import_user_catalog
from nomy_trader.market.ajaib_hints import run_reversal_hint_scan
from nomy_trader.market.daily_recheck import recheck_daily
from nomy_trader.providers.massive import MassiveClient, MassiveError
from nomy_trader.providers.sec_edgar import SecEdgarClient, SecEdgarError
from nomy_trader.providers.twelve_data import TwelveDataClient, TwelveDataError
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
            "ajaib-hints",
            "sec-filings",
        ],
    )
    parser.add_argument(
        "--symbol", help="Default: first candidate in the latest saved FMP scan"
    )
    parser.add_argument("--database", type=Path, default=Path("var/nomy-trader.sqlite"))
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("config/private_ajaib_us_stock.json"),
        help="Complete manually supplied Ajaib JSON response for ajaib-import",
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
    if args.command == "sec-filings" and not sec_user_agent:
        print("SEC_USER_AGENT is missing from environment or local .env")
        return 1
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
        if args.command == "ajaib-import":
            snapshot = import_user_catalog(engine, args.input, datetime.now(UTC))
            print(
                f"CATALOGUE_IMPORTED {snapshot.catalog_entry_count} source entries | "
                f"{len(snapshot.symbols)} working symbols | {snapshot.revision}"
            )
            return 0
        if args.command == "ajaib-hints":
            scan = run_reversal_hint_scan(engine, datetime.now(UTC))
            print(
                f"RESEARCH_HINTS {len(scan.candidates)} of {scan.source_entries} "
                f"from {scan.catalogue_revision}"
            )
            for candidate in scan.candidates:
                month = (
                    str(candidate.one_month_percent)
                    if candidate.one_month_percent is not None
                    else "unavailable"
                )
                print(
                    f"{candidate.symbol} | ${candidate.price} | "
                    f"1d {candidate.one_day_percent}% | "
                    f"1w {candidate.one_week_percent}% | "
                    f"1m {month}%"
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
