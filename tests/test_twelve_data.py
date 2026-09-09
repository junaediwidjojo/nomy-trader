import traceback
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from nomy_trader.providers.twelve_data import (
    TwelveDataClient,
    TwelveDataError,
    TwelveDataRateLimitError,
)


def payload():
    return {
        "symbol": "BANL",
        "timestamp": int(datetime(2026, 9, 8, 20, tzinfo=UTC).timestamp()),
        "close": "9.01",
        "previous_close": "10.00",
        "volume": "1200",
        "unneeded_provider_field": "ignored",
    }


def test_quote_reserves_one_credit_and_keeps_key_out_of_url():
    reservations = []

    def send(request):
        assert request.headers["Authorization"] == "apikey private-key"
        assert "private-key" not in str(request.url)
        return httpx.Response(200, json=payload())

    with TwelveDataClient(
        "private-key",
        reservations.append,
        httpx.Client(transport=httpx.MockTransport(send)),
    ) as client:
        quote = client.quote("BANL")
    assert reservations == [1]
    assert quote.close == Decimal("9.01")


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_failure_is_sanitized(status):
    client = TwelveDataClient(
        "private-key",
        lambda _: None,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status, text="private-key")
            )
        ),
    )
    with pytest.raises(TwelveDataError) as error:
        client.quote("BANL")
    assert "private-key" not in str(error.value)


def test_rate_and_invalid_payload_are_rejected():
    rate = TwelveDataClient(
        "private-key",
        lambda _: None,
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429))),
    )
    with pytest.raises(TwelveDataRateLimitError):
        rate.quote("BANL")
    invalid = TwelveDataClient(
        "private-key",
        lambda _: None,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"symbol": "BANL"})
            )
        ),
    )
    with pytest.raises(TwelveDataError):
        invalid.quote("BANL")


def test_timeout_does_not_chain_provider_detail():
    client = TwelveDataClient(
        "private-key",
        lambda _: None,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(httpx.ReadTimeout("private-key"))
            )
        ),
    )
    with pytest.raises(TwelveDataError) as error:
        client.quote("BANL")
    assert "private-key" not in "".join(traceback.format_exception(error.value))
