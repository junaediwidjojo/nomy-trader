"""Named TradingAgents configuration profiles for sandbox comparisons."""

from __future__ import annotations

from nomy_trader.domain.models import Contract, Text

ProfileOverrides = dict[str, str]


class TradingAgentsProfile(Contract):
    name: Text
    description: Text
    env_overrides: dict[str, str]


BASELINE_MODEL = "accounts/fireworks/models/gpt-oss-120b"
HIGH_MODEL = "accounts/fireworks/models/qwen3p8-max"

DEFAULT_RUN_PROFILE = "baseline"
CONFIRM_BUY_PROFILE = "high_model_two_round_debate"

TRADINGAGENTS_PROFILES: dict[str, TradingAgentsProfile] = {
    "baseline": TradingAgentsProfile(
        name="baseline",
        description="Production default: 1 debate round, gpt-oss-120b.",
        env_overrides={
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS": "1",
            "TRADINGAGENTS_MAX_RISK_ROUNDS": "1",
            "TRADINGAGENTS_DEEP_THINK_LLM": BASELINE_MODEL,
            "TRADINGAGENTS_QUICK_THINK_LLM": BASELINE_MODEL,
        },
    ),
    "two_round_debate": TradingAgentsProfile(
        name="two_round_debate",
        description="Two investment and risk debate rounds, gpt-oss-120b.",
        env_overrides={
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS": "2",
            "TRADINGAGENTS_MAX_RISK_ROUNDS": "2",
        },
    ),
    "high_model_one_round": TradingAgentsProfile(
        name="high_model_one_round",
        description="One debate round with Qwen3.8 Max on Fireworks.",
        env_overrides={
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS": "1",
            "TRADINGAGENTS_MAX_RISK_ROUNDS": "1",
            "TRADINGAGENTS_DEEP_THINK_LLM": HIGH_MODEL,
            "TRADINGAGENTS_QUICK_THINK_LLM": HIGH_MODEL,
        },
    ),
    "high_model_two_round_debate": TradingAgentsProfile(
        name="high_model_two_round_debate",
        description="Two debate rounds with Qwen3.8 Max on Fireworks.",
        env_overrides={
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS": "2",
            "TRADINGAGENTS_MAX_RISK_ROUNDS": "2",
            "TRADINGAGENTS_DEEP_THINK_LLM": HIGH_MODEL,
            "TRADINGAGENTS_QUICK_THINK_LLM": HIGH_MODEL,
        },
    ),
}


def profile_env_overrides(profile_name: str) -> ProfileOverrides:
    merged = dict(TRADINGAGENTS_PROFILES["baseline"].env_overrides)
    merged.update(TRADINGAGENTS_PROFILES[profile_name].env_overrides)
    return merged


def default_run_env_overrides() -> ProfileOverrides:
    """Env overrides for the daily `run` command."""
    return profile_env_overrides(DEFAULT_RUN_PROFILE)


def confirm_buy_env_overrides() -> ProfileOverrides:
    """Env overrides for bullish-signal confirmation runs."""
    return profile_env_overrides(CONFIRM_BUY_PROFILE)
