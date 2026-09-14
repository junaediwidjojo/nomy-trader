"""Local cache for TradingAgents subprocess results."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nomy_trader.domain.models import Contract, Text, Timestamp


class TradingAgentsCacheEntry(Contract):
    symbol: Text
    profile_key: Text
    analyzed_at: Timestamp
    runner_payload: dict[str, object]


def profile_cache_key(env_overrides: dict[str, str]) -> str:
    canonical = json.dumps(env_overrides, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def cache_ttl() -> timedelta:
    hours = int(os.getenv("TRADINGAGENTS_CACHE_TTL_HOURS", "48"))
    if hours < 1:
        raise ValueError("TRADINGAGENTS_CACHE_TTL_HOURS must be positive")
    return timedelta(hours=hours)


def default_cache_dir(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[3]
    return root / "var" / "tradingagents_analysis_cache"


def cache_path(
    symbol: str,
    profile_key: str,
    *,
    project_root: Path | None = None,
) -> Path:
    return default_cache_dir(project_root) / f"{symbol.upper()}_{profile_key}.json"


def load_fresh_cache_entry(
    symbol: str,
    profile_key: str,
    *,
    now: datetime,
    project_root: Path | None = None,
) -> TradingAgentsCacheEntry | None:
    path = cache_path(symbol, profile_key, project_root=project_root)
    if not path.exists():
        return None
    try:
        entry = TradingAgentsCacheEntry.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if entry.symbol.upper() != symbol.upper() or entry.profile_key != profile_key:
        return None
    age = now - entry.analyzed_at.astimezone(UTC)
    if age > cache_ttl():
        return None
    return entry


def save_cache_entry(
    entry: TradingAgentsCacheEntry,
    *,
    project_root: Path | None = None,
) -> Path:
    path = cache_path(entry.symbol, entry.profile_key, project_root=project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entry.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return path
