from datetime import UTC, datetime

import httpx
import pytest

from nomy_trader.providers.sec_edgar import SecEdgarClient, SecEdgarError, SecFiling
from nomy_trader.research import evidence_from_sec_document


def client(handler):
    return SecEdgarClient(
        "nomy-trader contact@example.test", transport=httpx.MockTransport(handler)
    )


def test_finds_cik_and_returns_only_requested_filing_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "nomy-trader contact@example.test"
        if request.url.path.endswith("company_tickers_exchange.json"):
            return httpx.Response(
                200, json={"fields": ["cik", "ticker"], "data": [[123, "BRZE"]]}
            )
        return httpx.Response(
            200,
            json={
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000123-26-000001", "0000123-26-000002"],
                        "filingDate": ["2026-09-01", "2026-08-01"],
                        "form": ["8-K", "10-Q"],
                        "primaryDocument": ["event.htm", "quarter.htm"],
                    }
                }
            },
        )

    with client(handler) as sec:
        filings = sec.latest_filings("BRZE", {"8-K"})

    assert len(filings) == 1
    assert filings[0].cik == "0000000123"
    assert filings[0].form == "8-K"
    assert filings[0].document_url.endswith("/000012326000001/event.htm")


def test_blocks_invalid_contact_and_sanitizes_network_failures():
    with pytest.raises(ValueError, match="contact email"):
        SecEdgarClient("nomy-trader")
    with client(lambda _: httpx.Response(403, text="untrusted response")) as sec:
        with pytest.raises(SecEdgarError, match="SEC request failed"):
            sec.cik_for_symbol("BRZE")


def filing() -> SecFiling:
    return SecFiling(
        cik="0000000123",
        form="8-K",
        filed_at=datetime(2026, 9, 9, tzinfo=UTC),
        accession_number="0000123-26-000001",
        primary_document="event.htm",
        document_url="https://www.sec.gov/Archives/example/event.htm",
    )


def test_retrieves_bounded_primary_document_with_immutable_evidence():
    with client(lambda _: httpx.Response(200, content=b"<html>Fact</html>")) as sec:
        document = sec.retrieve_document(filing())

    evidence = evidence_from_sec_document("event-1", document)
    assert (
        document.content_hash
        == "c839d7f14c4dde949261933829df1381ec33e2df3c30c0461f3086fd218e2afa"
    )
    assert evidence.id == "sec:0000123-26-000001:event.htm"
    assert evidence.primary is True
    assert evidence.content_or_licensed_reference == "<html>Fact</html>"


def test_rejects_oversized_or_non_text_primary_document():
    oversized = b"x" * (SecEdgarClient.max_document_bytes + 1)
    with client(lambda _: httpx.Response(200, content=oversized)) as sec:
        with pytest.raises(SecEdgarError, match="size limit"):
            sec.retrieve_document(filing())
    with client(lambda _: httpx.Response(200, content=b"\xff")) as sec:
        with pytest.raises(SecEdgarError, match="UTF-8"):
            sec.retrieve_document(filing())
