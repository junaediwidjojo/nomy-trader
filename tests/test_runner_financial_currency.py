import sys
from types import ModuleType, SimpleNamespace

import pytest

from scripts.run_tradingagents_single import (
    _install_financial_currency_context,
    _pin_tool_symbols,
)


@pytest.mark.parametrize("missing_currency", [False, True])
def test_financial_tool_labels_native_currency_and_blocks_unknown_units(
    monkeypatch: pytest.MonkeyPatch, missing_currency: bool
) -> None:
    calls = []
    requested_symbols = []

    def ticker(symbol):
        calls.append(symbol)
        return SimpleNamespace(
            info={
                "currency": "USD",
                "financialCurrency": None if missing_currency else "CNY",
            }
        )

    yf = ModuleType("yfinance")
    yf.Ticker = ticker
    package = ModuleType("tradingagents")
    dataflows = ModuleType("tradingagents.dataflows")
    stats = ModuleType("tradingagents.dataflows.stockstats_utils")
    stats.yf_with_timeout = lambda func, seconds: func()
    for name, module in {
        "yfinance": yf,
        "tradingagents": package,
        "tradingagents.dataflows": dataflows,
        "tradingagents.dataflows.stockstats_utils": stats,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    def financials(ticker, curr_date=None):
        requested_symbols.append(ticker)
        return f"Revenue: 30110000000\nAs of: {curr_date}"

    tool = SimpleNamespace(name="get_fundamentals", func=financials)
    node = SimpleNamespace(tools_by_name={tool.name: tool})
    graph = SimpleNamespace(tool_nodes={"first": node, "shared": node})
    observed = {}
    _install_financial_currency_context(graph, observed)
    overrides = []
    _pin_tool_symbols(graph, "NTES", overrides)
    if missing_currency:
        with pytest.raises(ValueError, match="currency unavailable"):
            tool.func("NTES", curr_date="2026-10-22")
        assert observed == {}
        return
    result = tool.func("NTEN", curr_date="2026-10-22")
    assert "Financial statement currency: CNY" in result
    assert "Share-price / market-cap currency: USD" in result
    assert "Revenue: 30110000000" in result
    assert "As of: 2026-10-22" in result
    assert result.count("Provider currency metadata") == 1
    assert tool.func(ticker="NTES").startswith("# Provider currency metadata")
    assert calls == ["NTES"]
    assert requested_symbols == ["NTES", "NTES"]
    assert overrides[0]["requested"] == "NTEN"
    assert overrides[0]["used"] == "NTES"
    assert observed["NTES"]["financial_currency"] == "CNY"
