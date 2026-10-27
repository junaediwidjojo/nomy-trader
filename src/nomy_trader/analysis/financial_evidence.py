"""Deterministic summaries of dated provider statement cells.

These check arithmetic and units, not agreement with issuer filings.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

METRICS = {
    "income_statement": (
        "Total Revenue",
        "Net Income",
        "Operating Income",
        "Gross Profit",
        "EBITDA",
    ),
    "balance_sheet": (
        "Total Assets",
        "Stockholders Equity",
        "Total Debt",
        "Cash And Cash Equivalents",
    ),
    "cashflow": ("Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"),
}
REQUIRED_METRICS = {
    "income_statement": ("Total Revenue", "Net Income"),
    "balance_sheet": ("Total Assets",),
    "cashflow": ("Operating Cash Flow",),
}


def statement_cells(
    text: str, statement: str, as_of: date
) -> dict[str, dict[str, str]]:
    """Parse explicit dates and finite numbers; never infer fiscal-year labels."""
    if not isinstance(text, str):
        raise ValueError(f"Unsupported financial response: {statement}")
    if "(annual)" in text:
        raise ValueError("Annual statement cannot be labeled quarterly")
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    rows = list(csv.reader(io.StringIO(body.strip())))
    headers = [i for i, row in enumerate(rows) if len(row) > 1 and row[0] == ""]
    if len(headers) != 1:
        raise ValueError(f"Missing dated CSV: {statement}")
    rows = rows[headers[0] :]
    dates = [date.fromisoformat(value[:10]) for value in rows[0][1:]]
    if len(set(dates)) != len(dates):
        raise ValueError(f"Duplicate statement dates: {statement}")
    cells: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        if not row or row[0] not in METRICS[statement]:
            continue
        metric = row[0]
        if metric in cells or len(row) != len(dates) + 1:
            raise ValueError(f"Invalid/duplicate financial row: {metric}")
        values = {}
        for day, value in zip(dates, row[1:], strict=True):
            if day > as_of or not value.strip():
                continue
            try:
                number = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f"Non-numeric financial cell: {metric}") from exc
            if not number.is_finite():
                raise ValueError(f"Non-finite financial cell: {metric}")
            values[day.isoformat()] = format(number, "f")
        cells[metric] = dict(sorted(values.items(), reverse=True))
    if any(not cells.get(key) for key in REQUIRED_METRICS[statement]):
        raise ValueError(f"Required financial evidence missing: {statement}")
    return cells


@dataclass(frozen=True)
class FinancialEvidenceRequest:
    symbol: str
    as_of: str
    financial_currency: str
    quote_currency: str
    statements: dict[str, str]


def financial_evidence(request: FinancialEvidenceRequest) -> dict[str, object]:
    """Keep source hashes, exact dates and independently reproducible arithmetic."""
    for currency in (request.financial_currency, request.quote_currency):
        if re.fullmatch(r"[A-Z]{3}", currency) is None:
            raise ValueError("Financial and quote currencies must be ISO codes")
    cutoff = date.fromisoformat(request.as_of)
    tables = {
        name: statement_cells(request.statements[name], name, cutoff)
        for name in METRICS
    }
    income = tables["income_statement"]
    latest = max(income["Total Revenue"])
    revenue = Decimal(income["Total Revenue"][latest])
    profit = income["Net Income"].get(latest)
    calculations = {}
    if profit is not None and revenue > 0:
        calculations["net_income_divided_by_total_revenue_percent"] = {
            "period_end": latest,
            "value": format(Decimal(profit) / revenue * 100, ".4f"),
            "formula": "Net Income / Total Revenue * 100",
        }
    for metric in ("Total Revenue", "Net Income"):
        values = income[metric]
        end = max(values)
        try:
            prior = date.fromisoformat(end).replace(year=int(end[:4]) - 1).isoformat()
        except ValueError:
            continue
        previous = values.get(prior)
        if previous is not None and Decimal(previous) > 0:
            calculations[f"{metric}_yoy_percent"] = {
                "period_end": end,
                "prior_period_end": prior,
                "value": format(
                    (Decimal(values[end]) / Decimal(previous) - 1) * 100, ".4f"
                ),
                "formula": "(current / matching year-ago period - 1) * 100",
            }
    evidence: dict[str, object] = {
        "symbol": request.symbol,
        "as_of": request.as_of,
        "source": "configured financial tools",
        "frequency": "quarterly",
        "financial_currency": request.financial_currency,
        "quote_currency": request.quote_currency,
        "amount_units": "raw currency units",
        "tables": tables,
        "calculations": calculations,
        "source_sha256": {
            name: hashlib.sha256(text.encode()).hexdigest()
            for name, text in request.statements.items()
        },
        "issuer_verified": False,
    }
    evidence["sha256"] = hashlib.sha256(
        json.dumps(evidence, sort_keys=True).encode()
    ).hexdigest()
    return evidence


def render_financial_evidence(evidence: dict[str, object]) -> str:
    """Render the ledger verbatim; models do not rewrite financial tables."""
    return (
        "# Deterministic quarterly financial evidence\n"
        "Source: configured provider, NOT independently verified issuer facts.\n"
        "Dates are period-end dates, not publication dates. Missing comparisons "
        "are unavailable, not zero. Do not infer fiscal years or compare "
        "quarterly values to annual values. No FX or ADS conversion is performed.\n"
        "The income/revenue ratio uses the provider's exact metric definitions; "
        "it is not NIM, gross revenue margin or a comparable peer-bank ratio.\n"
        "EPS/share fields are withheld because ADS/share units are unverified.\n"
        "Qualitative debate claims, forecasts, peer multiples and event narratives "
        "are unverified model commentary. "
        "No holdings or sizing inputs are supplied.\n\n"
        + json.dumps(evidence, indent=2)
    )
