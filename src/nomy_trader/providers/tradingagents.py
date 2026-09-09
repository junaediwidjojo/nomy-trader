"""Bounded adapter boundary for supplementary TradingAgents commentary."""

import hashlib
import subprocess
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nomy_trader.domain.models import Text
from nomy_trader.research import EvidencePacket
from nomy_trader.signals import TradingAgentsReview, TradingAgentsReviewStatus


class TradingAgentsRunnerError(RuntimeError):
    """Sanitized runner failure; report output is untrusted data."""


class CuratedEvidence(BaseModel):
    """Provenance-only fact supplied to the external reviewer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Text
    kind: Text
    source: Text
    publisher: Text
    published_at: datetime
    primary: bool


class CuratedObservation(BaseModel):
    """An assessed business-risk state, excluding raw document content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Text
    status: Text
    evidence_ids: tuple[Text, ...]


class CuratedTradingAgentsRequest(BaseModel):
    """Small serializable request that excludes raw webpage or filing text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: Text
    event_id: Text
    as_of: datetime
    evidence: tuple[CuratedEvidence, ...] = Field(min_length=1)
    observations: tuple[CuratedObservation, ...] = Field(min_length=1)


class RunnerReviewStatus(StrEnum):
    SUPPORTS = "SUPPORTS"
    CHALLENGES = "CHALLENGES"


class _RunnerResponse(BaseModel):
    """Strict response contract for a separate, locally configured runner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: RunnerReviewStatus
    summary: Text
    evidence_ids: tuple[Text, ...] = Field(min_length=1)


def curated_request(packet: EvidencePacket) -> CuratedTradingAgentsRequest:
    """Build a minimal fact packet. Document bodies never cross this boundary."""
    return CuratedTradingAgentsRequest(
        symbol=packet.symbol,
        event_id=packet.event_id,
        as_of=packet.as_of,
        evidence=tuple(
            CuratedEvidence(
                id=item.id,
                kind=item.kind,
                source=item.source,
                publisher=item.publisher,
                published_at=item.published_at,
                primary=item.primary,
            )
            for item in packet.evidence
        ),
        observations=tuple(
            CuratedObservation(
                kind=item.kind.value,
                status=item.status.value,
                evidence_ids=item.evidence_ids,
            )
            for item in packet.observations
        ),
    )


class TradingAgentsSubprocessAdapter:
    """Run an explicitly configured curated-fact runner with a hard timeout."""

    def __init__(self, command: tuple[str, ...], timeout_seconds: int) -> None:
        if not command:
            raise ValueError("TradingAgents runner command is required")
        if timeout_seconds <= 0:
            raise ValueError("TradingAgents timeout must be positive")
        self._command = command
        self._timeout_seconds = timeout_seconds

    def review(
        self, packet: EvidencePacket, *, reviewed_at: datetime
    ) -> TradingAgentsReview:
        request = curated_request(packet)
        try:
            completed = subprocess.run(
                self._command,
                input=request.model_dump_json(),
                capture_output=True,
                check=False,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired):
            return _unavailable(packet.symbol, reviewed_at)
        if completed.returncode != 0:
            return _unavailable(packet.symbol, reviewed_at)
        try:
            response = _RunnerResponse.model_validate_json(completed.stdout)
        except ValidationError:
            return _unavailable(packet.symbol, reviewed_at)
        packet_ids = {evidence.id for evidence in packet.evidence}
        if not set(response.evidence_ids).issubset(packet_ids):
            return _unavailable(packet.symbol, reviewed_at)
        return TradingAgentsReview(
            symbol=packet.symbol,
            reviewed_at=reviewed_at,
            status=TradingAgentsReviewStatus(response.status.value),
            summary=response.summary,
            report_hash=hashlib.sha256(completed.stdout.encode()).hexdigest(),
            evidence_ids=response.evidence_ids,
        )


def _unavailable(symbol: str, reviewed_at: datetime) -> TradingAgentsReview:
    return TradingAgentsReview(
        symbol=symbol,
        reviewed_at=reviewed_at,
        status=TradingAgentsReviewStatus.UNAVAILABLE,
        summary="TradingAgents review was unavailable or failed validation.",
    )
