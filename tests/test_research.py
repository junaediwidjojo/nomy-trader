from datetime import UTC, datetime, timedelta

import pytest

from nomy_trader.domain.models import Evidence
from nomy_trader.research import (
    BusinessRiskKind,
    BusinessRiskObservation,
    CitedReview,
    EvidencePacket,
    ObservationStatus,
    ResearchGateStatus,
    ReviewRole,
    evaluate_business_gate,
    validate_review,
)

AT = datetime(2026, 9, 9, tzinfo=UTC)


def evidence() -> Evidence:
    return Evidence(
        id="filing",
        event_id="event-1",
        kind="filing",
        source="SEC",
        publisher="Issuer",
        published_at=AT - timedelta(days=1),
        retrieved_at=AT - timedelta(hours=1),
        version_available_at=AT - timedelta(days=1),
        availability_proof="official filing",
        content_hash="a" * 64,
        content_or_licensed_reference="https://example.test/filing",
        primary=True,
    )


def packet(event_status: ObservationStatus = ObservationStatus.CLEAR) -> EvidencePacket:
    return EvidencePacket(
        symbol="BRZE",
        event_id="event-1",
        as_of=AT,
        evidence=(evidence(),),
        observations=tuple(
            BusinessRiskObservation(
                kind=kind,
                status=(
                    event_status
                    if kind == BusinessRiskKind.EVENT_EXPLANATION
                    else ObservationStatus.CLEAR
                ),
                evidence_ids=("filing",),
                assessed_at=AT,
            )
            for kind in BusinessRiskKind
        ),
    )


def test_clean_packet_is_only_ready_for_review():
    result = evaluate_business_gate(packet())
    assert result.status == ResearchGateStatus.READY_FOR_REVIEW
    assert result.blocking_reasons == ()


def test_unknown_event_blocks_research():
    result = evaluate_business_gate(packet(ObservationStatus.UNKNOWN))
    assert result.status == ResearchGateStatus.BLOCKED
    assert result.blocking_reasons == ("event_explanation_missing_or_unresolved",)


def test_packet_and_review_reject_bad_evidence_references():
    with pytest.raises(ValueError, match="at least 5 items"):
        EvidencePacket.model_validate({**packet().model_dump(), "observations": []})
    review = CitedReview(
        role=ReviewRole.BULL,
        summary="Temporary move",
        claims=("A claim",),
        evidence_ids=("missing",),
    )
    with pytest.raises(ValueError, match="outside packet"):
        validate_review(review, packet())
