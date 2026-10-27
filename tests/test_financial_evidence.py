from datetime import date

import pytest

from nomy_trader.analysis.financial_evidence import (
    FinancialEvidenceRequest,
    financial_evidence,
    render_financial_evidence,
    statement_cells,
)


def statements():
    return {
        "income_statement": (
            "# Income Statement data for NTES (quarterly)\n"
            ",2025-06-30,2026-03-31,2026-06-30\n"
            "Total Revenue,27890000000,30590000000,30110000000\n"
            "Net Income,8600000000,10670000000,6980000000\n"
            "Diluted EPS,13.35,16.55,10.85\n"
        ),
        "balance_sheet": ",2026-06-30\nTotal Assets,232210000000\n",
        "cashflow": ",2026-06-30\nOperating Cash Flow,9970000000\n",
    }


def build(data=None):
    return financial_evidence(
        FinancialEvidenceRequest(
            symbol="NTES",
            as_of="2026-10-27",
            financial_currency="CNY",
            quote_currency="USD",
            statements=data or statements(),
        )
    )


def test_date_order_currency_and_arithmetic_are_not_model_generated():
    evidence = build()
    income = evidence["tables"]["income_statement"]
    assert list(income["Total Revenue"]) == ["2026-06-30", "2026-03-31", "2025-06-30"]
    assert income["Net Income"]["2026-06-30"] == "6980000000"
    assert "Diluted EPS" not in income
    assert evidence["financial_currency"] == "CNY"
    assert evidence["quote_currency"] == "USD"
    assert evidence["issuer_verified"] is False
    growth = evidence["calculations"]["Net Income_yoy_percent"]
    assert growth["prior_period_end"] == "2025-06-30"
    assert growth["value"] == "-18.8372"
    ratio = evidence["calculations"]["net_income_divided_by_total_revenue_percent"]
    assert ratio["value"] == "23.1817"
    assert build()["sha256"] == evidence["sha256"]
    report = render_financial_evidence(evidence)
    assert "not publication dates" in report
    assert "NOT independently verified" in report


def test_sequential_periods_are_not_repaired_into_year_over_year():
    data = statements()
    data["income_statement"] = (
        ",2026-06-30,2026-03-31\nTotal Revenue,10,20\nNet Income,1,2\n"
    )
    evidence = build(data)
    assert "Total Revenue_yoy_percent" not in evidence["calculations"]
    assert "Net Income_yoy_percent" not in evidence["calculations"]


def test_currency_annotations_before_csv_do_not_replace_dated_header():
    data = statements()
    data["income_statement"] = (
        "# Provider currency metadata\nFinancial statement currency: CNY\n"
        "Share-price / market-cap currency: USD\n"
        "Preserve currency; no FX conversion.\n\n" + data["income_statement"]
    )
    assert build(data)["calculations"] == build()["calculations"]


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "1,000", "not a number"])
def test_bad_cells_fail_closed(bad):
    text = f",2026-06-30\nTotal Revenue,{bad}\nNet Income,1\n"
    with pytest.raises(ValueError):
        statement_cells(text, "income_statement", date(2026, 10, 27))


def test_future_columns_and_missing_comparisons_are_withheld():
    text = ",2026-12-31,2026-06-30\nTotal Revenue,999,10\nNet Income,99,1\n"
    values = statement_cells(text, "income_statement", date(2026, 10, 27))
    assert values["Total Revenue"] == {"2026-06-30": "10"}


@pytest.mark.parametrize(
    "text",
    [
        "Error retrieving statement",
        ",2026-06-30\nEBITDA,12\n",
        ",2026-06-30,2026-06-30\nTotal Revenue,1,2\nNet Income,1,2\n",
        "# income (annual)\n,2026-06-30\nTotal Revenue,10\nNet Income,1\n",
    ],
)
def test_unsupported_missing_duplicate_or_annual_evidence_is_rejected(text):
    with pytest.raises(ValueError):
        statement_cells(text, "income_statement", date(2026, 10, 27))
