"""Run a bounded discovery/recheck cycle with local credentials."""

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from dotenv import load_dotenv

from nomy_trader.market.daily_recheck import recheck_daily
from nomy_trader.providers.massive import MassiveClient, MassiveError
from nomy_trader.storage.database import open_database, upgrade
from nomy_trader.storage.rate_limit import RateLimited, reserve_request
from nomy_trader.storage.schema import scan_runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recheck a logged FMP candidate using daily bars"
    )
    parser.add_argument("command", choices=["recheck"])
    parser.add_argument(
        "--symbol", help="Default: first candidate in the latest saved FMP scan"
    )
    parser.add_argument("--database", type=Path, default=Path("var/nomy-trader.sqlite"))
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)
    key = os.getenv("MASSIVE_API_KEY", "")
    if not key:
        print("MASSIVE_API_KEY is missing from environment or local .env")
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
    except (MassiveError, RateLimited, ValueError) as exc:
        print(f"Recheck stopped: {exc}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
