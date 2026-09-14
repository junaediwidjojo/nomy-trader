"""Fetch the Ajaib US-stock screener JSON using a user-supplied web session."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Self
from urllib.parse import urlencode

import httpx

from nomy_trader.market.ajaib_catalog import validate_catalog_payload


class AjaibUsStockError(RuntimeError):
    """Sanitized fetch failure safe for local logs."""


class AjaibUsStockAuthError(AjaibUsStockError):
    """Missing or rejected session credentials."""


class AjaibUsStockClient:
    """Read-only client for the same endpoint the Ajaib web app uses."""

    default_base_url = "https://ajaib.co.id/api/us-stock"

    def __init__(
        self,
        *,
        cookie: str | None = None,
        authorization: str | None = None,
        user_agent: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._cookie = (cookie or os.getenv("AJAIB_COOKIE", "")).strip()
        self._authorization = (
            authorization or os.getenv("AJAIB_AUTHORIZATION", "")
        ).strip()
        self._user_agent = (
            user_agent
            or os.getenv(
                "AJAIB_USER_AGENT",
                (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36"
                ),
            )
        ).strip()
        self._base_url = (
            base_url or os.getenv("AJAIB_US_STOCK_URL", self.default_base_url)
        ).strip()
        self._client = client
        self._owns_client = client is None

    def __enter__(self) -> Self:
        if self._client is None:
            self._client = httpx.Client(timeout=60.0, follow_redirects=True)
        return self

    def __exit__(self, *args: object) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        if not self._cookie and not self._authorization:
            raise AjaibUsStockAuthError(
                "Set AJAIB_COOKIE and/or AJAIB_AUTHORIZATION in local .env "
                "(copy from a logged-in browser request to /api/us-stock)."
            )
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self._user_agent,
            "Referer": "https://ajaib.co.id/",
            "Origin": "https://ajaib.co.id",
        }
        if self._cookie:
            headers["Cookie"] = self._cookie
        if self._authorization:
            headers["Authorization"] = self._authorization
        return headers

    def fetch_catalog(
        self,
        *,
        page_size: int | None = None,
        sort_type: str = "PCT_CHANGE_1_DAY",
        sort_direction: str = "DESC",
        filter_type: str = "",
    ) -> dict[str, object]:
        if self._client is None:
            raise RuntimeError("client not opened; use AjaibUsStockClient as context")
        size = page_size or int(os.getenv("AJAIB_US_STOCK_PAGE_SIZE", "10000"))
        query = urlencode(
            {
                "page_size": size,
                "filter_type": filter_type,
                "sort_type": sort_type,
                "sort_direction": sort_direction,
            }
        )
        url = f"{self._base_url}?{query}"
        response = self._client.get(url, headers=self._headers())
        body = response.text
        if response.status_code in {401, 403}:
            if body.lstrip().startswith("<!DOCTYPE") or "cloudflare" in body.lower():
                raise AjaibUsStockAuthError(
                    "Ajaib returned Cloudflare/HTML instead of JSON. Refresh "
                    "AJAIB_COOKIE (and cf_clearance if present) from DevTools."
                )
            raise AjaibUsStockAuthError(
                f"Ajaib rejected the session (HTTP {response.status_code})."
            )
        if response.status_code != 200:
            raise AjaibUsStockError(
                f"Ajaib US-stock fetch failed with HTTP {response.status_code}."
            )
        try:
            payload: dict[str, object] = response.json()
        except json.JSONDecodeError as exc:
            raise AjaibUsStockError("Ajaib response was not JSON.") from exc
        try:
            validate_catalog_payload(payload)
        except ValueError as exc:
            raise AjaibUsStockError(str(exc)) from exc
        return payload


def fetch_us_stock_catalog_to_file(output_path: Path) -> int:
    """Download the screener JSON and write it to disk."""
    with AjaibUsStockClient() as client:
        payload = client.fetch_catalog()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise AjaibUsStockError("Ajaib response missing result block.")
    count = result.get("count")
    if not isinstance(count, int):
        raise AjaibUsStockError("Ajaib response missing result.count.")
    return count
