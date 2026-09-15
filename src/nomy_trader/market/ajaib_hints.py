"""Local research hints derived from a user-supplied Ajaib snapshot."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import Field
from sqlalchemy import Engine

from nomy_trader.domain.models import (
    Contract,
    Finite,
    Nonnegative,
    Positive,
    Text,
    Timestamp,
)
from nomy_trader.market.ajaib_catalog import (
    _RawInstrument,
    load_latest_imported_snapshot_and_response,
)
from nomy_trader.storage.schema import scan_runs

# Eligibility v4 (2026-09-14): requiring a same-day decline excluded selloffs
# that had begun to stabilize, which are the overreaction cases worth reviewing.
# Eligibility now rests on a week or month drawdown; FMP confirms the rest.
MIN_HINT_PRICE = Decimal("5")
MIN_HINT_MARKET_CAP = 250_000_000
MIN_ONE_WEEK_DECLINE_PERCENT = Decimal("4")
MIN_ONE_MONTH_DECLINE_PERCENT = Decimal("10")


class AjaibReversalHint(Contract):
    """A price-pattern observation; never a recommendation or eligibility pass."""

    symbol: Text
    issuer_name: Text
    price: Positive
    market_cap: int = Field(gt=MIN_HINT_MARKET_CAP)
    one_day_percent: Finite
    one_week_percent: Finite
    one_month_percent: Finite | None


class AjaibHintRejection(Contract):
    symbol: Text
    reasons: tuple[Text, ...] = Field(min_length=1)


class PriorityPolicy(Contract):
    """Versioned, explainable ordering policy for already eligible hints."""

    version: Text
    one_day_weight: Nonnegative
    one_week_weight: Nonnegative
    one_month_weight: Nonnegative
    one_month_floor: Finite
    one_month_context_cap_fraction: Nonnegative


DEFAULT_PRIORITY_POLICY = PriorityPolicy(
    version="ajaib-priority-v3",
    # AMGN pattern: large weekly drawdown that has already stopped falling.
    # Day-crash ranking buried that setup at rank 37.
    one_day_weight=Decimal("0.25"),
    one_week_weight=Decimal("1.0"),
    one_month_weight=Decimal("0.25"),
    one_month_floor=Decimal("-10.0"),
    one_month_context_cap_fraction=Decimal("0.25"),
)


class PriorityBreakdown(Contract):
    one_day_severity: Nonnegative
    one_week_severity: Nonnegative
    one_month_reversal_context: Nonnegative
    total: Nonnegative


class RankedAjaibHint(Contract):
    rank: int = Field(strict=True, gt=0)
    hint: AjaibReversalHint
    breakdown: PriorityBreakdown


class AjaibReversalHintScan(Contract):
    observed_at: Timestamp
    catalogue_revision: Text
    catalogue_retrieved_at: Timestamp
    source_entries: int = Field(gt=0)
    candidates: tuple[AjaibReversalHint, ...]
    priority_policy: PriorityPolicy
    ranked_candidates: tuple[RankedAjaibHint, ...]
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
    ordered_candidates = tuple(
        sorted(candidates, key=lambda item: item.one_day_percent)
    )
    scan = AjaibReversalHintScan(
        observed_at=now,
        catalogue_revision=snapshot.revision,
        catalogue_retrieved_at=snapshot.retrieved_at,
        source_entries=raw.result.count,
        candidates=ordered_candidates,
        priority_policy=DEFAULT_PRIORITY_POLICY,
        ranked_candidates=rank_reversal_hints(
            ordered_candidates, DEFAULT_PRIORITY_POLICY
        ),
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


def rank_reversal_hints(
    candidates: tuple[AjaibReversalHint, ...], policy: PriorityPolicy
) -> tuple[RankedAjaibHint, ...]:
    """Rank eligible hints without altering eligibility or filling missing values."""
    if len({candidate.symbol for candidate in candidates}) != len(candidates):
        raise ValueError("ranked candidates must have unique symbols")
    scored: list[tuple[AjaibReversalHint, PriorityBreakdown]] = []
    for candidate in candidates:
        day = max(Decimal("0"), -candidate.one_day_percent) * policy.one_day_weight
        week = max(Decimal("0"), -candidate.one_week_percent) * policy.one_week_weight
        severity = day + week
        context = Decimal("0")
        if candidate.one_month_percent is not None:
            raw_context = (
                max(Decimal("0"), candidate.one_month_percent - policy.one_month_floor)
                * policy.one_month_weight
            )
            context = min(
                raw_context,
                severity * policy.one_month_context_cap_fraction,
            )
        scored.append(
            (
                candidate,
                PriorityBreakdown(
                    one_day_severity=day,
                    one_week_severity=week,
                    one_month_reversal_context=context,
                    total=severity + context,
                ),
            )
        )
    ordered = sorted(scored, key=lambda item: (-item[1].total, item[0].symbol))
    return tuple(
        RankedAjaibHint(rank=index, hint=candidate, breakdown=breakdown)
        for index, (candidate, breakdown) in enumerate(ordered, start=1)
    )


def _has_drawdown(instrument: _RawInstrument) -> bool:
    """A week or a month of weakness qualifies; either window may carry it."""
    week = instrument.price_1_week
    if week is not None and week.pct_change <= -MIN_ONE_WEEK_DECLINE_PERCENT:
        return True
    month = instrument.price_1_month
    return month is not None and month.pct_change <= -MIN_ONE_MONTH_DECLINE_PERCENT


def _rejection_reasons(instrument: _RawInstrument) -> tuple[str, ...]:
    reasons: list[str] = []
    if instrument.price <= MIN_HINT_PRICE:
        reasons.append("price_not_above_5")
    if instrument.market_cap <= MIN_HINT_MARKET_CAP:
        reasons.append("market_cap_not_above_250m")
    if instrument.price_1_day is None:
        reasons.append("missing_one_day_change")
    if instrument.price_1_week is None:
        reasons.append("missing_one_week_change")
    elif not _has_drawdown(instrument):
        reasons.append("no_week_or_month_drawdown")
    return tuple(reasons)
