from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, ValidationError

from nomy_trader.analysis.cache import profile_cache_key
from nomy_trader.analysis.profiles import (
    confirm_buy_env_overrides,
    default_run_env_overrides,
)
from scripts import run_tradingagents_single as runner


class PortfolioDecision(BaseModel):
    rating: str
    investment_thesis: str


def test_native_binding_sends_schema_and_preserves_required_thesis() -> None:
    decision = PortfolioDecision(rating="Hold", investment_thesis="Mixed evidence.")
    bound = Mock()
    bound.invoke.return_value = decision
    llm = Mock()
    llm.with_structured_output.return_value = bound
    invoker = runner._JsonSchemaInvoker(llm, PortfolioDecision)

    assert invoker.invoke("Debate evidence") is decision
    llm.with_structured_output.assert_called_once_with(
        PortfolioDecision, method="json_schema", strict=True
    )
    prompt = bound.invoke.call_args.args[0]
    assert prompt.startswith("Debate evidence")
    assert '"required": ["rating", "investment_thesis"]' in prompt
    assert "do not invent" in prompt


def test_message_prompt_retains_evidence_and_adds_json_instructions() -> None:
    llm = Mock()
    messages = [{"role": "user", "content": "Evidence"}]
    runner._JsonSchemaInvoker(llm, PortfolioDecision).invoke(messages)
    forwarded = llm.with_structured_output.return_value.invoke.call_args.args[0]
    assert forwarded[0] == messages[0]
    assert "JSON" in forwarded[-1]["content"]
    assert len(messages) == 1


def test_binding_reaches_agent_local_imports_and_capture_still_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRADINGAGENTS_STRUCTURED_METHOD", "json_schema")
    modules = []
    originals = []
    for name in runner._STRUCTURED_CONSUMERS:
        module = SimpleNamespace(bind_structured=Mock())
        originals.append(module.bind_structured)
        monkeypatch.setitem(runner.sys.modules, name, module)
        modules.append(module)
    runner._install_structured_binding()
    llm = Mock()
    llm.model_copy.return_value = llm

    # Simulate the original bug: a provider response with no investment_thesis.
    def invalid_response(prompt: object) -> PortfolioDecision:
        return PortfolioDecision.model_validate({"rating": "Hold"})

    llm.with_structured_output.return_value.invoke.side_effect = invalid_response
    bound = modules[1].bind_structured(llm, PortfolioDecision, "Portfolio Manager")
    for module, original in zip(modules, originals, strict=True):
        module.bind_structured(llm, PortfolioDecision, "Trader")
        original.assert_called_once_with(llm, PortfolioDecision, "Trader")
        assert isinstance(
            module.bind_structured(llm, PortfolioDecision, "Portfolio Manager"),
            runner._JsonSchemaInvoker,
        )
    captured: dict = {}
    errors: dict = {}
    runner._install_structured_capture(captured, errors)
    plain = Mock()
    plain.invoke.return_value.content = "**Rating**: Buy"
    result = modules[1].invoke_structured_or_freetext(
        bound, plain, "Evidence", str, "Portfolio Manager"
    )
    assert result == "**Rating**: Buy"
    assert captured["Portfolio Manager"] is None
    assert "investment_thesis" in errors["Portfolio Manager"]
    assert "ValidationError" in errors["Portfolio Manager"]


def test_default_binding_unchanged_and_unknown_method_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Mock()
    module = SimpleNamespace(bind_structured=original)
    monkeypatch.setitem(runner.sys.modules, runner._STRUCTURED_CONSUMERS[1], module)
    monkeypatch.delenv("TRADINGAGENTS_STRUCTURED_METHOD", raising=False)
    runner._install_structured_binding()
    assert module.bind_structured is original
    monkeypatch.setenv("TRADINGAGENTS_STRUCTURED_METHOD", "typo")
    with pytest.raises(ValueError, match="unsupported structured method"):
        runner._install_structured_binding()


def test_required_thesis_cannot_be_omitted_or_filled_by_invoker() -> None:
    llm = Mock()
    llm.with_structured_output.return_value.invoke.side_effect = (
        ValidationError.from_exception_data(
            "PortfolioDecision",
            [{"type": "missing", "loc": ("investment_thesis",), "input": {}}],
        )
    )
    with pytest.raises(ValidationError):
        runner._JsonSchemaInvoker(llm, PortfolioDecision).invoke("Evidence")


def test_corrected_confirmation_profile_does_not_reuse_old_cache() -> None:
    current = confirm_buy_env_overrides()
    old = {
        k: v
        for k, v in current.items()
        if k
        not in {"TRADINGAGENTS_STRUCTURED_METHOD", "TRADINGAGENTS_PORTFOLIO_MAX_TOKENS"}
    }
    assert current["TRADINGAGENTS_STRUCTURED_METHOD"] == "json_schema"
    assert current["TRADINGAGENTS_PORTFOLIO_MAX_TOKENS"] == "8192"
    assert profile_cache_key(current) != profile_cache_key(old)
    assert "TRADINGAGENTS_STRUCTURED_METHOD" not in default_run_env_overrides()


def test_portfolio_budget_clones_client_without_changing_debate_budget() -> None:
    llm = Mock()
    decision_llm = llm.model_copy.return_value
    runner._JsonSchemaInvoker(llm, PortfolioDecision, max_tokens=8192)
    llm.model_copy.assert_called_once_with(update={"max_tokens": 8192})
    decision_llm.with_structured_output.assert_called_once_with(
        PortfolioDecision, method="json_schema", strict=True
    )
    llm.with_structured_output.assert_not_called()
    with pytest.raises(ValueError, match="budget must be positive"):
        runner._JsonSchemaInvoker(llm, PortfolioDecision, max_tokens=0)
