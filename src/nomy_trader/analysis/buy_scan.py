"""Summarize TradingAgents outputs for learning-oriented buy scans."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from nomy_trader.analysis.bullish import is_bullish_signal, qualifies_on_upside
from nomy_trader.domain.models import Contract, Finite, Text, Timestamp


class _AnalysisRow(Protocol):
    symbol: str
    signal: str | None
    confirmatory: _AnalysisRow | None
    price_target: str | None
    entry_hint: str | None
    executive_summary: str | None
    reference_price: Decimal | None
    target_upside: Decimal | None


class BuyCandidateRow(Contract):
    symbol: Text
    primary_signal: Text
    trigger: Text
    confirm_signal: Text | None = None
    status: Text
    price_target: Text | None = None
    target_upside: Finite | None = None
    entry_hint: Text | None = None
    executive_summary: Text | None = None


class BuyScanSummary(Contract):
    observed_at: Timestamp
    catalogue_revision: Text | None
    candidates_screened: int
    symbols_analyzed: int
    primary_bullish: tuple[Text, ...]
    upside_candidates: tuple[Text, ...]
    confirmed_bullish: tuple[Text, ...]
    disputed_bullish: tuple[Text, ...]
    rows: tuple[BuyCandidateRow, ...]


def summarize_buy_candidates(
    results: tuple[_AnalysisRow, ...],
    *,
    observed_at: Timestamp,
    catalogue_revision: Text | None,
    candidates_screened: int,
) -> BuyScanSummary:
    primary_bullish: list[str] = []
    upside_candidates: list[str] = []
    confirmed_bullish: list[str] = []
    disputed_bullish: list[str] = []
    rows: list[BuyCandidateRow] = []

    for item in results:
        bullish = is_bullish_signal(item.signal)
        upside = qualifies_on_upside(
            item.signal,
            item.price_target,
            getattr(item, "reference_price", None),
        )
        if not bullish and not upside:
            continue
        if bullish:
            primary_bullish.append(item.symbol)
        else:
            upside_candidates.append(item.symbol)
        confirm_signal: str | None = None
        status = "primary_only"
        if item.confirmatory is not None:
            confirm_signal = item.confirmatory.signal
            if is_bullish_signal(item.confirmatory.signal):
                status = "confirmed"
                confirmed_bullish.append(item.symbol)
            else:
                status = "disputed"
                disputed_bullish.append(item.symbol)
        rows.append(
            BuyCandidateRow(
                symbol=item.symbol,
                primary_signal=str(item.signal),
                trigger="bullish_signal" if bullish else "upside_target",
                confirm_signal=confirm_signal,
                status=status,
                price_target=item.price_target,
                target_upside=getattr(item, "target_upside", None),
                entry_hint=item.entry_hint,
                executive_summary=item.executive_summary,
            )
        )

    return BuyScanSummary(
        observed_at=observed_at,
        catalogue_revision=catalogue_revision,
        candidates_screened=candidates_screened,
        symbols_analyzed=len(results),
        primary_bullish=tuple(primary_bullish),
        upside_candidates=tuple(upside_candidates),
        confirmed_bullish=tuple(confirmed_bullish),
        disputed_bullish=tuple(disputed_bullish),
        rows=tuple(rows),
    )


def write_buy_scan_summary(
    summary: BuyScanSummary,
    *,
    project_root: Path | None = None,
) -> Path:
    root = project_root or Path(__file__).resolve().parents[3]
    path = root / "var" / "buy_candidates_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary.model_dump(mode="json"), indent=2)
    path.write_text(payload, encoding="utf-8")
    return path
