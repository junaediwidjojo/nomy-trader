import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, ValidationError

from scripts import run_tradingagents_single as runner


def test_decision_calls_receive_canonical_ledger_not_only_debate_claims():
    class Decision(BaseModel):
        rating: str

    llm = Mock()
    invoker = runner._JsonSchemaInvoker(llm, Decision)
    context = {}
    invoker.financial_context = context
    # The graph is bound before provider data is fetched.
    context["evidence"] = {"financial_currency": "CNY", "tables": {"profit": 698}}
    invoker.invoke("Unverified debate claims")
    prompt = llm.with_structured_output.return_value.invoke.call_args.args[0]
    assert '"financial_currency": "CNY"' in prompt
    assert '"profit": 698' in prompt
    assert "issuer agreement is unverified" in prompt


def test_wrong_tickers_are_scoped_before_provider_calls_and_audited():
    calls = []

    def fundamentals(ticker, curr_date=None):
        calls.append((ticker, curr_date))
        return ticker

    def bars(symbol, start_date, end_date):
        calls.append((symbol, start_date, end_date))
        return symbol

    tools = {
        "fundamentals": SimpleNamespace(name="fundamentals", func=fundamentals),
        "bars": SimpleNamespace(name="bars", func=bars),
    }
    node = SimpleNamespace(tools_by_name=tools)
    graph = SimpleNamespace(tool_nodes={"a": node, "shared": node})
    observed = []
    runner._pin_tool_symbols(graph, "NTES", observed)
    assert tools["fundamentals"].func("NTEN", "2026-10-27") == "NTES"
    assert (
        tools["bars"].func(symbol="NU", start_date="2026-10-01", end_date="2026-10-27")
        == "NTES"
    )
    assert calls == [("NTES", "2026-10-27"), ("NTES", "2026-10-01", "2026-10-27")]
    assert len(observed) == 2
    assert observed[0] == {
        "tool": "fundamentals",
        "field": "ticker",
        "requested": "NTEN",
        "used": "NTES",
    }
    tools["fundamentals"].func(ticker="NTES")
    assert len(observed) == 2


def test_native_portfolio_schema_requires_real_horizon(monkeypatch):
    class Portfolio(BaseModel):
        rating: str
        time_horizon: str | None = None

    monkeypatch.setenv("TRADINGAGENTS_STRUCTURED_METHOD", "json_schema")
    module = SimpleNamespace(bind_structured=Mock())
    monkeypatch.setitem(sys.modules, runner._STRUCTURED_CONSUMERS[1], module)
    runner._install_structured_binding()
    llm = Mock()
    llm.model_copy.return_value = llm
    module.bind_structured(llm, Portfolio, "Portfolio Manager")
    schema = llm.with_structured_output.call_args.args[0]
    assert "time_horizon" in schema.model_json_schema()["required"]
    for invalid in [None, "", "  "]:
        with pytest.raises(ValidationError):
            schema.model_validate({"rating": "Hold", "time_horizon": invalid})
    with pytest.raises(ValidationError):
        schema.model_validate({"rating": "Hold"})
    assert schema.model_validate({"rating": "Hold", "time_horizon": "Next earnings"})


@pytest.mark.parametrize("broken_statement", [False, True])
def test_financial_node_uses_provider_cells_without_model_rewrite(
    monkeypatch, broken_statement
):
    setup = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "tradingagents.graph.setup", setup)
    messages = ModuleType("langchain_core.messages")
    messages.AIMessage = lambda **kwargs: SimpleNamespace(**kwargs)
    stats = ModuleType("tradingagents.dataflows.stockstats_utils")
    stats.yf_with_timeout = lambda func, seconds: func()
    for name, module in {
        "langchain_core": ModuleType("langchain_core"),
        "langchain_core.messages": messages,
        "tradingagents": ModuleType("tradingagents"),
        "tradingagents.dataflows": ModuleType("tradingagents.dataflows"),
        "tradingagents.dataflows.stockstats_utils": stats,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    bodies = {
        "fundamentals": (
            "Name: NTES\nPE Ratio (TTM): 17\nEPS (TTM): 10.85\nBook Value: 3"
        ),
        "income_statement": ",2026-06-30\nTotal Revenue,10\nNet Income,1\n",
        "balance_sheet": ",2026-06-30\nTotal Assets,20\n",
        "cashflow": ",2026-06-30\nOperating Cash Flow,3\n",
    }
    if broken_statement:
        bodies["income_statement"] = "Error retrieving income statement"
    tools = {}
    for name, body in bodies.items():
        tools[f"get_{name}"] = SimpleNamespace(func=Mock(return_value=body))
    context = {
        "ticker": "NTES",
        "currencies": {
            "NTES": {
                "financial_currency": "CNY",
                "quote_currency": "USD",
            }
        },
        "graph": SimpleNamespace(
            tool_nodes={"fundamentals": SimpleNamespace(tools_by_name=tools)}
        ),
    }
    runner._install_financial_analyst(context)
    llm = Mock()
    node = setup.create_fundamentals_analyst(llm)
    if broken_statement:
        with pytest.raises(ValueError):
            node({"trade_date": "2026-10-27"})
        assert "evidence" not in context
        return
    result = node({"trade_date": "2026-10-27"})
    assert "Deterministic quarterly financial evidence" in result["fundamentals_report"]
    assert "EPS (TTM):" not in result["fundamentals_report"]
    assert "Book Value:" not in result["fundamentals_report"]
    assert (
        context["evidence"]["calculations"][
            "net_income_divided_by_total_revenue_percent"
        ]["value"]
        == "10.0000"
    )
    tools["get_income_statement"].func.assert_called_once_with(
        ticker="NTES",
        curr_date="2026-10-27",
        freq="quarterly",
    )
    llm.invoke.assert_not_called()
