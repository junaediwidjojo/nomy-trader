"""Offline, cited research gates for shortlisted symbols."""

from enum import StrEnum

from pydantic import Field, model_validator

from nomy_trader.domain.models import Contract, Evidence, References, Text, Timestamp
from nomy_trader.domain.validation import unique_facts
from nomy_trader.providers.sec_edgar import SecDocument


class ObservationStatus(StrEnum):
    CLEAR = "CLEAR"
    PRESENT = "PRESENT"
    UNKNOWN = "UNKNOWN"


class BusinessRiskKind(StrEnum):
    BANKRUPTCY = "BANKRUPTCY"
    DELISTING_OR_HALT = "DELISTING_OR_HALT"
    GOING_CONCERN = "GOING_CONCERN"
    MATERIAL_DILUTION = "MATERIAL_DILUTION"
    EVENT_EXPLANATION = "EVENT_EXPLANATION"


class BusinessRiskObservation(Contract):
    kind: BusinessRiskKind
    status: ObservationStatus
    evidence_ids: References
    assessed_at: Timestamp


class EvidencePacket(Contract):
    symbol: Text
    event_id: Text
    as_of: Timestamp
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    observations: tuple[BusinessRiskObservation, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def complete_and_available(self) -> "EvidencePacket":
        facts = unique_facts(self.evidence, "id")
        if len(facts) != len(self.evidence):
            raise ValueError("duplicate evidence is not allowed")
        evidence_by_id = {item.id: item for item in facts}
        if any(item.event_id != self.event_id for item in facts):
            raise ValueError("evidence event does not match packet")
        kinds = {item.kind for item in self.observations}
        if kinds != set(BusinessRiskKind):
            raise ValueError("packet must contain each required observation once")
        for observation in self.observations:
            if observation.assessed_at > self.as_of:
                raise ValueError("observation follows packet as-of time")
            for evidence_id in observation.evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    raise ValueError("observation cites missing evidence")
                if evidence.version_available_at > observation.assessed_at:
                    raise ValueError("observation cites unavailable evidence")
        return self


class ResearchGateStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"


class ResearchGateResult(Contract):
    status: ResearchGateStatus
    blocking_reasons: tuple[Text, ...]


def evaluate_business_gate(packet: EvidencePacket) -> ResearchGateResult:
    """Fail closed; READY_FOR_REVIEW is deliberately not a buy approval."""
    observations = {item.kind: item for item in packet.observations}
    reasons: list[str] = []
    for kind in (
        BusinessRiskKind.BANKRUPTCY,
        BusinessRiskKind.DELISTING_OR_HALT,
        BusinessRiskKind.GOING_CONCERN,
        BusinessRiskKind.MATERIAL_DILUTION,
    ):
        status = observations[kind].status
        if status == ObservationStatus.PRESENT:
            reasons.append(f"{kind.value.lower()}_present")
        elif status == ObservationStatus.UNKNOWN:
            reasons.append(f"{kind.value.lower()}_unknown")
    event = observations[BusinessRiskKind.EVENT_EXPLANATION].status
    if event != ObservationStatus.CLEAR:
        reasons.append("event_explanation_missing_or_unresolved")
    return ResearchGateResult(
        status=(
            ResearchGateStatus.BLOCKED
            if reasons
            else ResearchGateStatus.READY_FOR_REVIEW
        ),
        blocking_reasons=tuple(reasons),
    )


class ReviewRole(StrEnum):
    BULL = "BULL"
    BEAR = "BEAR"


class CitedReview(Contract):
    role: ReviewRole
    summary: Text
    claims: tuple[Text, ...] = Field(min_length=1)
    evidence_ids: References


def validate_review(review: CitedReview, packet: EvidencePacket) -> None:
    available_ids = {item.id for item in packet.evidence}
    if not set(review.evidence_ids).issubset(available_ids):
        raise ValueError("review cites evidence outside packet")


def evidence_from_sec_document(event_id: str, document: SecDocument) -> Evidence:
    """Preserve SEC provenance without treating filing content as instructions."""
    filing = document.filing
    return Evidence(
        id=f"sec:{filing.accession_number}:{filing.primary_document}",
        event_id=event_id,
        kind=f"sec_{filing.form.lower().replace('-', '_')}",
        source="SEC EDGAR",
        publisher="SEC EDGAR",
        published_at=filing.filed_at,
        retrieved_at=document.retrieved_at,
        version_available_at=filing.filed_at,
        availability_proof=(
            f"SEC accession {filing.accession_number}; {filing.document_url}"
        ),
        content_hash=document.content_hash,
        content_or_licensed_reference=document.content,
        primary=True,
    )
