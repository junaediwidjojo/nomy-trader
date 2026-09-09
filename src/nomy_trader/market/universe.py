"""Versioned manual seed universe; it narrows discovery but proves no eligibility."""

import json
from decimal import Decimal
from pathlib import Path

from pydantic import Field, ValidationError, model_validator

from nomy_trader.domain.models import Contract, Positive, Text, Timestamp
from nomy_trader.providers.fmp import Loser


class UniverseSecurity(Contract):
    symbol: Text = Field(pattern=r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
    issuer: Text
    security_type: str = "Common Stock"

    @model_validator(mode="after")
    def common_stock_only(self) -> "UniverseSecurity":
        if self.security_type != "Common Stock":
            raise ValueError("manual universe permits common stocks only")
        return self


class UniversePolicy(Contract):
    minimum_price_usd: Positive
    minimum_market_cap_usd: Positive


class ManualUniverse(Contract):
    revision: Text
    reviewed_at: Timestamp
    reviewer: Text
    policy: UniversePolicy
    limitation: Text
    securities: tuple[UniverseSecurity, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_symbols(self) -> "ManualUniverse":
        symbols = [security.symbol for security in self.securities]
        if len(symbols) != len(set(symbols)):
            raise ValueError("manual universe has duplicate symbols")
        return self


def load_manual_universe(path: Path) -> ManualUniverse:
    try:
        return ManualUniverse.model_validate(json.loads(path.read_text()))
    except (OSError, ValueError, ValidationError):
        raise ValueError("manual universe file is invalid") from None


def shortlist(losers: tuple[Loser, ...], universe: ManualUniverse) -> tuple[Loser, ...]:
    """Keep only reviewed symbols at the approved discovery price floor."""
    allowed = {security.symbol for security in universe.securities}
    floor: Decimal = universe.policy.minimum_price_usd
    return tuple(
        loser for loser in losers if loser.symbol in allowed and loser.price > floor
    )
