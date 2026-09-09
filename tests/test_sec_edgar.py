import httpx
import pytest

from nomy_trader.providers.sec_edgar import SecEdgarClient, SecEdgarError


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
