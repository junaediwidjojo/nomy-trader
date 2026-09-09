"""Bounded read-only SEC EDGAR filing-metadata client."""

from datetime import UTC, datetime
from time import monotonic, sleep
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nomy_trader.domain.models import Text


class SecEdgarError(RuntimeError):
    """Sanitized failure; response bodies can contain untrusted content."""


class SecFiling(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cik: Text = Field(pattern=r"^\d{10}$")
    form: Text
    filed_at: datetime
    accession_number: Text
    primary_document: Text
    document_url: Text


class _TickerFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    fields: tuple[str, ...]
    data: tuple[tuple[Any, ...], ...]


class _RecentFilings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    accessionNumber: tuple[str, ...]
    filingDate: tuple[str, ...]
    form: tuple[str, ...]
    primaryDocument: tuple[str, ...]


class _Submissions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    filings: dict[str, _RecentFilings]


class SecEdgarClient:
    """Filing metadata only; no document fetches, submissions, or credentials."""

    ticker_url = "https://www.sec.gov/files/company_tickers_exchange.json"
    submissions_base_url = "https://data.sec.gov/submissions"

    def __init__(
        self, user_agent: str, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        if "@" not in user_agent or len(user_agent.strip()) < 8:
            raise ValueError("SEC_USER_AGENT must contain a contact email address")
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=15,
            transport=transport,
        )
        self._next_request_at = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SecEdgarClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def cik_for_symbol(self, symbol: str) -> str:
        payload = self._get_json(self.ticker_url)
        try:
            ticker_file = _TickerFile.model_validate(payload)
            ticker_index = ticker_file.fields.index("ticker")
            cik_index = ticker_file.fields.index("cik")
        except (ValidationError, ValueError) as error:
            raise SecEdgarError("SEC ticker file has an unsupported shape") from error
        matches = [
            row[cik_index]
            for row in ticker_file.data
            if len(row) > max(ticker_index, cik_index)
            and str(row[ticker_index]).upper() == symbol.upper()
        ]
        if len(matches) != 1:
            raise SecEdgarError("SEC ticker identity is missing or ambiguous")
        return f"{int(matches[0]):010d}"

    def latest_filings(
        self, symbol: str, forms: set[str], limit: int = 10
    ) -> tuple[SecFiling, ...]:
        if limit < 1:
            raise ValueError("filing limit must be positive")
        cik = self.cik_for_symbol(symbol)
        payload = self._get_json(f"{self.submissions_base_url}/CIK{cik}.json")
        try:
            recent = _Submissions.model_validate(payload).filings["recent"]
        except (KeyError, ValidationError) as error:
            raise SecEdgarError(
                "SEC submissions response has an unsupported shape"
            ) from error
        columns = zip(
            recent.accessionNumber,
            recent.filingDate,
            recent.form,
            recent.primaryDocument,
            strict=True,
        )
        filings: list[SecFiling] = []
        for accession, filed_date, form, primary_document in columns:
            if form not in forms:
                continue
            try:
                filed_at = datetime.fromisoformat(
                    f"{filed_date}T00:00:00+00:00"
                ).astimezone(UTC)
            except ValueError as error:
                raise SecEdgarError("SEC filing date is invalid") from error
            accession_path = accession.replace("-", "")
            filings.append(
                SecFiling(
                    cik=cik,
                    form=form,
                    filed_at=filed_at,
                    accession_number=accession,
                    primary_document=primary_document,
                    document_url=(
                        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                        f"{accession_path}/{primary_document}"
                    ),
                )
            )
            if len(filings) == limit:
                break
        return tuple(filings)

    def _get_json(self, url: str) -> object:
        try:
            wait_seconds = self._next_request_at - monotonic()
            if wait_seconds > 0:
                sleep(wait_seconds)
            response = self._client.get(url)
            self._next_request_at = monotonic() + 1.0
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SecEdgarError("SEC request failed") from error
