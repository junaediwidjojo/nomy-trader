"""Deterministic FMP profile gate before TradingAgents.

One /profile call per Ajaib hint. Quote and EOD history are not used because
the current FMP plan returns HTTP 402 on those routes. Failures reject the
symbol; they are not repaired. This is a research shortlist filter, not
eligibility or a buy signal.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Engine

from nomy_trader.domain.models import (
    Contract,
    Finite,
    Nonnegative,
    Positive,
    Text,
    Timestamp,
)
from nomy_trader.market.ajaib_hints import AjaibReversalHint, RankedAjaibHint
from nomy_trader.providers.fmp import CompanyProfile, FmpClient, FmpError
from nomy_trader.storage.quota import QuotaExhausted, QuotaWindow, reserve
from nomy_trader.storage.schema import scan_runs

MIN_FMP_PRICE = Decimal("5")
MIN_FMP_MARKET_CAP = Decimal("250000000")
# A fresh decline is not required: a selloff that stopped falling is the case
# worth reviewing. Only names that already recovered are dropped here.
MAX_LIVE_ONE_DAY_GAIN_PERCENT = Decimal("3")
MIN_AVG_DOLLAR_VOLUME = Decimal("5000000")
MAX_AJAIB_PRICE_DISAGREEMENT = Decimal("0.15")
# The free FMP plan allows 250 calls a day and each run re-checks the same top
# names, so an observation is reused for the rest of the session.
PROFILE_REUSE_TTL = timedelta(hours=8)
# Transient failures are never reused; only genuine observations are.
_TRANSIENT_REASONS = frozenset({"fmp_quota_exhausted", "fmp_profile_unavailable"})


class FmpPrescreenMetrics(Contract):
    close: Positive
    market_cap: Nonnegative | None = None
    one_day_percent: Finite | None = None
    avg_dollar_volume: Nonnegative | None = None
    is_etf: bool | None = None
    is_fund: bool | None = None


class FmpPrescreenRow(Contract):
    symbol: Text
    passed: bool
    reasons: tuple[Text, ...] = ()
    metrics: FmpPrescreenMetrics | None = None
    source: Text = "live"


class FmpPrescreenResult(Contract):
    checked_at: Timestamp
    passed: tuple[RankedAjaibHint, ...]
    rows: tuple[FmpPrescreenRow, ...]
    limitation: Text = (
        "FMP company-profile filter only; not eligibility, valuation, "
        "or a TradingAgents recommendation"
    )


def daily_fmp_prescreen_window(now: datetime) -> QuotaWindow:
    now = now.astimezone(UTC)
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    return QuotaWindow(
        id=f"fmp-prescreen-{start.date().isoformat()}",
        budget_name="fmp-prescreen",
        starts_at=start,
        ends_at=start + timedelta(days=1),
        call_limit=250,
    )


def evaluate_fmp_profile(
    hint: AjaibReversalHint, profile: CompanyProfile
) -> FmpPrescreenRow:
    reasons: list[str] = []
    if profile.symbol != hint.symbol:
        return FmpPrescreenRow(
            symbol=hint.symbol,
            passed=False,
            reasons=("fmp_symbol_mismatch",),
        )
    if profile.isEtf:
        reasons.append("fmp_is_etf")
    if profile.isFund:
        reasons.append("fmp_is_fund")
    if profile.isActivelyTrading is False:
        reasons.append("fmp_not_actively_trading")
    if profile.price <= MIN_FMP_PRICE:
        reasons.append("fmp_price_not_above_5")
    if profile.marketCap is None:
        reasons.append("fmp_market_cap_missing")
    elif profile.marketCap <= MIN_FMP_MARKET_CAP:
        reasons.append("fmp_market_cap_not_above_250m")
    if abs(profile.price / hint.price - 1) > MAX_AJAIB_PRICE_DISAGREEMENT:
        reasons.append("fmp_ajaib_price_disagreement")
    if profile.changePercentage is None:
        reasons.append("fmp_one_day_change_missing")
    elif profile.changePercentage > MAX_LIVE_ONE_DAY_GAIN_PERCENT:
        reasons.append("fmp_already_rebounded_above_3_percent")
    share_volume = profile.averageVolume
    if share_volume is None or share_volume <= 0:
        share_volume = profile.volume
    dollar_volume: Decimal | None = None
    if share_volume is None or share_volume <= 0:
        reasons.append("fmp_volume_missing")
    else:
        dollar_volume = share_volume * profile.price
        if dollar_volume < MIN_AVG_DOLLAR_VOLUME:
            reasons.append("fmp_avg_dollar_volume_below_5m")
    metrics = FmpPrescreenMetrics(
        close=profile.price,
        market_cap=profile.marketCap,
        one_day_percent=profile.changePercentage,
        avg_dollar_volume=dollar_volume,
        is_etf=profile.isEtf,
        is_fund=profile.isFund,
    )
    return FmpPrescreenRow(
        symbol=hint.symbol,
        passed=not reasons,
        reasons=tuple(reasons),
        metrics=metrics,
    )


def load_reusable_observations(
    engine: Engine, *, now: datetime
) -> dict[str, FmpPrescreenRow]:
    """Replay recent persisted prescreen rows so repeat runs cost no quota."""
    cutoff = now.astimezone(UTC) - PROFILE_REUSE_TTL
    reusable: dict[str, FmpPrescreenRow] = {}
    with engine.connect() as connection:
        records = connection.execute(
            sa.select(scan_runs.c.started_at, scan_runs.c.payload).order_by(
                scan_runs.c.started_at.asc()
            )
        )
        for started_at, payload in records:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if data.get("kind") != "fmp_prescreen":
                continue
            if datetime.fromisoformat(started_at) < cutoff:
                continue
            for raw in data.get("scan", {}).get("rows", ()):
                if set(raw.get("reasons", ())) & _TRANSIENT_REASONS:
                    continue
                try:
                    row = FmpPrescreenRow.model_validate(raw)
                except ValueError:
                    continue
                # Ascending order means the freshest observation wins.
                reusable[row.symbol] = row.model_copy(update={"source": "cache"})
    return reusable


def prescreen_ranked_hints(
    engine: Engine,
    client: FmpClient,
    ranked: tuple[RankedAjaibHint, ...],
    *,
    now: datetime,
    quota_window: QuotaWindow | None = None,
    reuse_recent: bool = True,
) -> FmpPrescreenResult:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("prescreen clock must be timezone-aware")
    now = now.astimezone(UTC)
    window = quota_window or daily_fmp_prescreen_window(now)
    reusable = load_reusable_observations(engine, now=now) if reuse_recent else {}
    rows: list[FmpPrescreenRow] = []
    passed: list[RankedAjaibHint] = []
    for item in ranked:
        cached = reusable.get(item.hint.symbol)
        if cached is not None:
            rows.append(cached)
            if cached.passed:
                passed.append(item)
            continue
        try:
            reserve(engine, window, now)
        except QuotaExhausted:
            rows.append(
                FmpPrescreenRow(
                    symbol=item.hint.symbol,
                    passed=False,
                    reasons=("fmp_quota_exhausted",),
                )
            )
            continue
        try:
            profile = client.profile(item.hint.symbol)
            row = evaluate_fmp_profile(item.hint, profile)
        except (FmpError, ValueError, TypeError):
            row = FmpPrescreenRow(
                symbol=item.hint.symbol,
                passed=False,
                reasons=("fmp_profile_unavailable",),
            )
        rows.append(row)
        if row.passed:
            passed.append(item)
    result = FmpPrescreenResult(checked_at=now, passed=tuple(passed), rows=tuple(rows))
    payload = {
        "kind": "fmp_prescreen",
        "scan": result.model_dump(mode="json"),
    }
    with engine.begin() as connection:
        connection.execute(
            scan_runs.insert().values(
                id=str(uuid4()),
                started_at=now.isoformat(),
                payload=json.dumps(payload),
            )
        )
    return result
