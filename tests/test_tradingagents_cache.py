from datetime import UTC, datetime, timedelta
from pathlib import Path

from nomy_trader.analysis.cache import (
    TradingAgentsCacheEntry,
    load_fresh_cache_entry,
    profile_cache_key,
    save_cache_entry,
)
from nomy_trader.analysis.profiles import default_run_env_overrides


def test_profile_cache_key_is_stable() -> None:
    overrides = default_run_env_overrides()
    assert profile_cache_key(overrides) == profile_cache_key(dict(overrides))


def test_cache_expires_after_ttl(tmp_path: Path) -> None:
    now = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    key = profile_cache_key(default_run_env_overrides())
    entry = TradingAgentsCacheEntry(
        symbol="NVO",
        profile_key=key,
        analyzed_at=now - timedelta(hours=49),
        runner_payload={"ticker": "NVO", "signal": "Hold", "final_decision": ""},
    )
    save_cache_entry(entry, project_root=tmp_path)
    assert (
        load_fresh_cache_entry("NVO", key, now=now, project_root=tmp_path) is None
    )


def test_cache_hit_within_ttl(tmp_path: Path) -> None:
    now = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    key = profile_cache_key(default_run_env_overrides())
    entry = TradingAgentsCacheEntry(
        symbol="NVO",
        profile_key=key,
        analyzed_at=now - timedelta(hours=10),
        runner_payload={"ticker": "NVO", "signal": "Hold", "final_decision": ""},
    )
    save_cache_entry(entry, project_root=tmp_path)
    loaded = load_fresh_cache_entry("NVO", key, now=now, project_root=tmp_path)
    assert loaded is not None
    assert loaded.runner_payload["signal"] == "Hold"
