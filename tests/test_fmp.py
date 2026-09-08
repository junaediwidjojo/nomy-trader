import httpx
import pytest

from nomy_trader.providers.fmp import (
    FmpAuthError,
    FmpClient,
    FmpError,
    FmpPayloadError,
    FmpRateLimitError,
)


def response(status: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status, json=payload, request=httpx.Request("GET", "https://test")
    )


def client(status: int, payload: object) -> FmpClient:
    return FmpClient(
        "secret-not-for-logs",
        httpx.Client(
            transport=httpx.MockTransport(lambda request: response(status, payload))
        ),
    )


def test_losers_are_typed_and_key_is_only_a_request_parameter():
    seen: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response(
            200,
            [
                {
                    "symbol": "ABC",
                    "name": "Example",
                    "price": 10,
                    "change": -2,
                    "changesPercentage": -16.7,
                    "exchange": "NASDAQ",
                }
            ],
        )

    transport_client = httpx.Client(transport=httpx.MockTransport(transport))
    fmp = FmpClient("secret-not-for-logs", transport_client)
    assert fmp.biggest_losers()[0].symbol == "ABC"
    assert seen[0].url.params["apikey"] == "secret-not-for-logs"
    assert "secret-not-for-logs" not in repr(fmp)


def test_quote_and_history_are_typed():
    quote = client(
        200,
        [
            {
                "symbol": "ABC",
                "name": "Example",
                "price": 10,
                "previousClose": 12,
                "marketCap": 1000000,
                "volume": 5000,
                "timestamp": 1778270400,
            }
        ],
    ).quote("ABC")
    assert quote.as_of.tzinfo is not None
    history = client(
        200, [{"symbol": "ABC", "date": "2026-05-08", "price": 10, "volume": 5000}]
    ).daily_history("ABC")
    assert history[0].volume == 5000


@pytest.mark.parametrize(
    "status,error",
    [
        (401, FmpAuthError),
        (403, FmpAuthError),
        (429, FmpRateLimitError),
        (500, FmpError),
    ],
)
def test_http_failure_is_sanitized(status, error):
    with pytest.raises(error) as raised:
        client(status, {"message": "secret-not-for-logs"}).biggest_losers()
    assert "secret-not-for-logs" not in str(raised.value)


@pytest.mark.parametrize("payload", [{}, [], [{"symbol": "ABC"}]])
def test_bad_payload_is_rejected(payload):
    with pytest.raises(FmpPayloadError):
        client(200, payload).biggest_losers()


def test_timeout_is_sanitized():
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret-not-for-logs")

    transport_client = httpx.Client(transport=httpx.MockTransport(timeout))
    fmp = FmpClient("secret-not-for-logs", transport_client)
    with pytest.raises(FmpError) as raised:
        fmp.biggest_losers()
    assert "secret-not-for-logs" not in str(raised.value)
