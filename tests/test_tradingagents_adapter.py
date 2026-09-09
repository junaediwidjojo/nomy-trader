from datetime import UTC, datetime
from subprocess import CompletedProcess, TimeoutExpired

from nomy_trader.providers.tradingagents import (
    TradingAgentsSubprocessAdapter,
    curated_request,
)
from nomy_trader.signals import TradingAgentsReviewStatus
from tests.test_research import packet

AT = datetime(2026, 9, 9, 10, tzinfo=UTC)


def test_curated_request_excludes_document_content() -> None:
    request = curated_request(packet())

    serialized = request.model_dump_json()
    assert request.symbol == "BRZE"
    assert "content_or_licensed_reference" not in serialized
    assert "https://example.test/filing" not in serialized


def test_runner_returns_hashed_cited_support(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def run(*args: object, **kwargs: object) -> CompletedProcess[str]:
        observed.update(kwargs)
        return CompletedProcess(
            args=(),
            returncode=0,
            stdout=(
                '{"status":"SUPPORTS","summary":"Cited facts support the thesis.",'
                '"evidence_ids":["filing"]}'
            ),
        )

    monkeypatch.setattr("subprocess.run", run)
    review = TradingAgentsSubprocessAdapter(("curated-runner",), 30).review(
        packet(), reviewed_at=AT
    )

    assert review.status == TradingAgentsReviewStatus.SUPPORTS
    assert review.evidence_ids == ("filing",)
    assert review.report_hash is not None
    assert observed["timeout"] == 30
    assert "content_or_licensed_reference" not in str(observed["input"])


def test_timeout_malformed_or_uncited_runner_output_becomes_unavailable(
    monkeypatch,
) -> None:
    adapter = TradingAgentsSubprocessAdapter(("curated-runner",), 30)

    def timeout(*_: object, **__: object) -> CompletedProcess[str]:
        raise TimeoutExpired("curated-runner", 30)

    monkeypatch.setattr("subprocess.run", timeout)
    assert (
        adapter.review(packet(), reviewed_at=AT).status
        == TradingAgentsReviewStatus.UNAVAILABLE
    )

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_args, **_kwargs: CompletedProcess(
            args=(), returncode=0, stdout='{"status":"SUPPORTS"}'
        ),
    )
    assert (
        adapter.review(packet(), reviewed_at=AT).status
        == TradingAgentsReviewStatus.UNAVAILABLE
    )

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_args, **_kwargs: CompletedProcess(
            args=(),
            returncode=0,
            stdout=(
                '{"status":"CHALLENGES","summary":"Uncited.",'
                '"evidence_ids":["outside-packet"]}'
            ),
        ),
    )
    assert (
        adapter.review(packet(), reviewed_at=AT).status
        == TradingAgentsReviewStatus.UNAVAILABLE
    )
