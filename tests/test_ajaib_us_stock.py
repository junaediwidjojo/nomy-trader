import httpx

from nomy_trader.providers.ajaib_us_stock import (
    AjaibUsStockAuthError,
    AjaibUsStockClient,
)


def _sample_payload() -> dict[str, object]:
    return {
        "err_message": "APPROVED/OK",
        "result": {
            "count": 1,
            "results": [
                {
                    "code": "AAA",
                    "name": "Alpha",
                    "price": 10,
                    "market_cap": 200_000_000,
                    "price_1_day": {"pct_change": -2},
                    "price_1_week": {"pct_change": -4},
                }
            ],
        },
    }


def test_fetch_catalog_parses_json_response() -> None:
    payload = _sample_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Cookie"] == "session=abc"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    with AjaibUsStockClient(cookie="session=abc", client=client) as ajaib:
        fetched = ajaib.fetch_catalog(page_size=10)
    assert fetched == payload


def test_fetch_catalog_rejects_cloudflare_html() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            403,
            text="<!DOCTYPE html><html>cloudflare</html>",
        )
    )
    client = httpx.Client(transport=transport)
    with AjaibUsStockClient(cookie="session=abc", client=client) as ajaib:
        try:
            ajaib.fetch_catalog()
        except AjaibUsStockAuthError as exc:
            assert "Cloudflare" in str(exc)
        else:
            raise AssertionError("expected auth error")
