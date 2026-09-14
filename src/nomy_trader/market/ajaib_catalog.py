"""Dated user-supplied Ajaib catalogue snapshots; no account or order access."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import Engine

from nomy_trader.domain.models import Contract, Finite, Positive, Text, Timestamp
from nomy_trader.storage.schema import scan_runs


class AjaibFilter(Contract):
    minimum_price_exclusive_usd: Positive
    minimum_market_cap_usd: Positive
    maximum_market_cap_usd: Positive | None = None

    @model_validator(mode="after")
    def ordered(self) -> "AjaibFilter":
        if (
            self.maximum_market_cap_usd is not None
            and self.minimum_market_cap_usd > self.maximum_market_cap_usd
        ):
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

    def accepts(self, symbol: str) -> bool:
        """Local catalogue membership; it does not assert order eligibility."""
        return symbol in self.symbols


def load_ajaib_catalog(path: Path) -> AjaibCatalogSnapshot:
    try:
        return AjaibCatalogSnapshot.model_validate(json.loads(path.read_text()))
    except (OSError, ValueError, ValidationError):
        raise ValueError("Ajaib catalogue snapshot is invalid") from None


class _RawModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class _RawPriceChange(_RawModel):
    pct_change: Finite


class _RawInstrument(_RawModel):
    code: Text = Field(pattern=r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
    name: Text
    price: Positive
    market_cap: int = Field(ge=0)
    price_1_day: _RawPriceChange | None = None
    price_1_week: _RawPriceChange | None = None
    price_1_month: _RawPriceChange | None = None


class _RawResult(_RawModel):
    count: int = Field(gt=0)
    results: tuple[_RawInstrument, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def count_matches(self) -> "_RawResult":
        if self.count != len(self.results):
            raise ValueError("Ajaib response count does not match results")
        return self


class _RawResponse(_RawModel):
    err_message: str
    result: _RawResult

    @model_validator(mode="after")
    def approved(self) -> "_RawResponse":
        if self.err_message != "APPROVED/OK":
            raise ValueError("Ajaib response was not approved")
        return self


def validate_catalog_payload(payload: object) -> _RawResponse:
    """Validate a live or saved Ajaib US-stock screener response."""
    try:
        return _RawResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Ajaib catalogue response is invalid") from exc


def import_user_catalog(
    engine: Engine, path: Path, now: datetime
) -> AjaibCatalogSnapshot:
    """Persist a supplied catalogue response and return its local working universe."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("catalogue import clock must be timezone-aware")
    now = now.astimezone(UTC)
    try:
        raw_payload = json.loads(path.read_text())
        raw = validate_catalog_payload(raw_payload)
    except OSError:
        raise ValueError("Ajaib catalogue response is invalid") from None
    symbols = tuple(
        instrument.code
        for instrument in raw.result.results
        if instrument.price > 5 and instrument.market_cap > 100_000_000
    )
    if len(symbols) != len(set(symbols)):
        raise ValueError("Ajaib catalogue response has duplicate symbols")
    snapshot = AjaibCatalogSnapshot(
        revision=f"ajaib-{now:%Y%m%dT%H%M%SZ}",
        retrieved_at=now,
        source="User-supplied Ajaib catalogue JSON with APPROVED/OK status",
        catalog_entry_count=raw.result.count,
        filter=AjaibFilter(
            minimum_price_exclusive_usd="5",
            minimum_market_cap_usd="100000000",
        ),
        limitation=(
            "Local catalogue reference only; common-stock classification and "
            "order eligibility remain unverified"
        ),
        symbols=symbols,
    )
    payload = {
        "kind": "ajaib_catalog_import",
        "snapshot": snapshot.model_dump(mode="json"),
        "raw_catalog": raw_payload,
    }
    with engine.begin() as connection:
        connection.execute(
            scan_runs.insert().values(
                id=str(uuid4()), started_at=now.isoformat(), payload=json.dumps(payload)
            )
        )
    return snapshot


def load_latest_imported_catalog(engine: Engine) -> AjaibCatalogSnapshot:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(scan_runs.c.payload).order_by(scan_runs.c.started_at.desc())
        )
        for row in rows:
            payload = json.loads(row[0])
            if payload.get("kind") == "ajaib_catalog_import":
                return AjaibCatalogSnapshot.model_validate(payload["snapshot"])
    raise ValueError("no imported Ajaib catalogue is available")


def load_latest_imported_response(engine: Engine) -> _RawResponse:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(scan_runs.c.payload).order_by(scan_runs.c.started_at.desc())
        )
        for row in rows:
            payload = json.loads(row[0])
            if payload.get("kind") == "ajaib_catalog_import":
                try:
                    return _RawResponse.model_validate(payload["raw_catalog"])
                except (KeyError, ValidationError):
                    raise ValueError(
                        "imported Ajaib catalogue response is invalid"
                    ) from None
    raise ValueError("no imported Ajaib catalogue is available")


def load_latest_imported_snapshot_and_response(
    engine: Engine,
) -> tuple[AjaibCatalogSnapshot, _RawResponse]:
    """Load one immutable import without mixing its provenance and raw rows."""
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(scan_runs.c.payload).order_by(scan_runs.c.started_at.desc())
        )
        for row in rows:
            payload = json.loads(row[0])
            if payload.get("kind") == "ajaib_catalog_import":
                try:
                    return (
                        AjaibCatalogSnapshot.model_validate(payload["snapshot"]),
                        _RawResponse.model_validate(payload["raw_catalog"]),
                    )
                except (KeyError, ValidationError):
                    raise ValueError(
                        "imported Ajaib catalogue response is invalid"
                    ) from None
    raise ValueError("no imported Ajaib catalogue is available")
