"""Local research hints derived from a user-supplied Ajaib snapshot."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import Field
from sqlalchemy import Engine

from nomy_trader.domain.models import Contract, Finite, Positive, Text, Timestamp
from nomy_trader.market.ajaib_catalog import (
    _RawInstrument,
    load_latest_imported_snapshot_and_response,
)
from nomy_trader.storage.schema import scan_runs


class AjaibReversalHint(Contract):
    """A price-pattern observation; never a recommendation or eligibility pass."""

    symbol: Text
    issuer_name: Text
    price: Positive
    market_cap: int = Field(gt=100_000_000)
    one_day_percent: Finite
    one_week_percent: Finite
    one_month_percent: Finite | None


class AjaibHintRejection(Contract):
    symbol: Text
    reasons: tuple[Text, ...] = Field(min_length=1)


class AjaibReversalHintScan(Contract):
    observed_at: Timestamp
    catalogue_revision: Text
    catalogue_retrieved_at: Timestamp
    source_entries: int = Field(gt=0)
    candidates: tuple[AjaibReversalHint, ...]
    rejections: tuple[AjaibHintRejection, ...]
    limitation: Text


def run_reversal_hint_scan(engine: Engine, now: datetime) -> AjaibReversalHintScan:
    """Persist a reproducible local shortlist and every non-candidate reason."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("hint scan clock must be timezone-aware")
    now = now.astimezone(UTC)
    snapshot, raw = load_latest_imported_snapshot_and_response(engine)
    candidates: list[AjaibReversalHint] = []
    rejections: list[AjaibHintRejection] = []
    for instrument in raw.result.results:
        reasons = _rejection_reasons(instrument)
        if reasons:
            rejections.append(
                AjaibHintRejection(symbol=instrument.code, reasons=reasons)
            )
            continue
        assert instrument.price_1_day is not None
        assert instrument.price_1_week is not None
        candidates.append(
            AjaibReversalHint(
                symbol=instrument.code,
                issuer_name=instrument.name,
                price=instrument.price,
                market_cap=instrument.market_cap,
                one_day_percent=instrument.price_1_day.pct_change,
                one_week_percent=instrument.price_1_week.pct_change,
                one_month_percent=(
                    instrument.price_1_month.pct_change
                    if instrument.price_1_month is not None
                    else None
                ),
            )
        )
    scan = AjaibReversalHintScan(
        observed_at=now,
        catalogue_revision=snapshot.revision,
        catalogue_retrieved_at=snapshot.retrieved_at,
        source_entries=raw.result.count,
        candidates=tuple(sorted(candidates, key=lambda item: item.one_day_percent)),
        rejections=tuple(rejections),
        limitation=(
            "Research hint only: no liquidity, spread, business validity, news, "
            "evidence, analyst, valuation, risk, plan or notification check occurred"
        ),
    )
    payload = {"kind": "ajaib_reversal_hints", "scan": scan.model_dump(mode="json")}
    with engine.begin() as connection:
        connection.execute(
            scan_runs.insert().values(
                id=str(uuid4()), started_at=now.isoformat(), payload=json.dumps(payload)
            )
        )
    return scan


def _rejection_reasons(instrument: _RawInstrument) -> tuple[str, ...]:
    reasons: list[str] = []
    if instrument.price <= 5:
        reasons.append("price_not_above_5")
    if instrument.market_cap <= 100_000_000:
        reasons.append("market_cap_not_above_100m")
    if instrument.price_1_day is None:
        reasons.append("missing_one_day_change")
    elif instrument.price_1_day.pct_change > -2:
        reasons.append("one_day_decline_not_at_least_2_percent")
    if instrument.price_1_week is None:
        reasons.append("missing_one_week_change")
    elif instrument.price_1_week.pct_change > -4:
        reasons.append("one_week_decline_not_at_least_4_percent")
    return tuple(reasons)
