"""Dated user-supplied Ajaib catalogue snapshots; no account or order access."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import Field, ValidationError, model_validator

from nomy_trader.domain.models import Contract, Positive, Text, Timestamp


class AjaibFilter(Contract):
    minimum_price_exclusive_usd: Positive
    minimum_market_cap_usd: Positive
    maximum_market_cap_usd: Positive

    @model_validator(mode="after")
    def ordered(self) -> "AjaibFilter":
        if self.minimum_market_cap_usd > self.maximum_market_cap_usd:
            raise ValueError("market-cap range is inverted")
        return self


class AjaibCatalogSnapshot(Contract):
    revision: Text
    retrieved_at: Timestamp
    source: Text
    catalog_entry_count: int = Field(gt=0)
    filter: AjaibFilter
    limitation: Text
    symbols: tuple[Text, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_symbols(self) -> "AjaibCatalogSnapshot":
        if len(self.symbols) != len(set(self.symbols)):
            raise ValueError("Ajaib snapshot has duplicate symbols")
        return self

    def accepts(self, symbol: str, now: datetime, max_age: timedelta) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("availability clock must be timezone-aware")
        if max_age <= timedelta(0):
            raise ValueError("snapshot max age must be positive")
        return (
            self.retrieved_at <= now <= self.retrieved_at + max_age
            and symbol in self.symbols
        )


def load_ajaib_catalog(path: Path) -> AjaibCatalogSnapshot:
    try:
        return AjaibCatalogSnapshot.model_validate(json.loads(path.read_text()))
    except (OSError, ValueError, ValidationError):
        raise ValueError("Ajaib catalogue snapshot is invalid") from None
