from datetime import timedelta

import pytest
from pydantic import ValidationError

from nomy_trader.domain.models import NotificationAttempt
from nomy_trader.domain.validation import validate_recommendation
from nomy_trader.fixtures import context
from nomy_trader.scenarios import AT


def changed(model, **updates):
    return type(model).model_validate({**model.model_dump(), **updates})


def test_complete_recommendation_round_trip():
    args = context()
    recommendation = args["recommendation"]
    assert (
        type(recommendation).model_validate_json(recommendation.model_dump_json())
        == recommendation
    )
    validate_recommendation(**args)


@pytest.mark.parametrize(
    "flag",
    [
        "data_available",
        "evidence_available",
        "model_available",
        "persistence_available",
        "quota_available",
    ],
)
def test_pipeline_failure(flag):
    args = context()
    args["health"] = changed(args["health"], **{flag: False})
    with pytest.raises(ValueError):
        validate_recommendation(**args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("notional", "499"),
        ("loss_at_stop", "24"),
        ("quantity", "5.5"),
    ],
)
def test_inconsistent_sizing(field, value):
    args = context()
    rec = args["recommendation"]
    args["recommendation"] = changed(rec, sizing=changed(rec.sizing, **{field: value}))
    with pytest.raises(ValueError):
        validate_recommendation(**args)


@pytest.mark.parametrize(
    "update",
    [
        {"now": AT + timedelta(seconds=601)},
        {"now": AT - timedelta(seconds=1)},
        {"now": AT.replace(tzinfo=None)},
    ],
)
def test_clock_and_expiry(update):
    with pytest.raises(ValueError):
        validate_recommendation(**{**context(), **update})


@pytest.mark.parametrize(
    "field,value",
    [
        ("policy_version", "other"),
        ("maximum_notional", "499"),
        ("risk_budget", "24"),
        ("quantity_increment", "2"),
        ("valid_until", AT),
    ],
)
def test_policy_context(field, value):
    args = context()
    rec = args["recommendation"]
    with pytest.raises(ValueError):
        inputs = changed(rec.sizing.inputs, **{field: value})
        args["recommendation"] = changed(rec, sizing=changed(rec.sizing, inputs=inputs))
        validate_recommendation(**args)


def test_margin_and_quote_age():
    for updates in (
        {"minimum_margin_of_safety": "0.5"},
        {"maximum_quote_age_seconds": 1},
    ):
        args = context()
        args["policy"] = changed(args["policy"], **updates)
        args["now"] = AT + timedelta(seconds=2)
        with pytest.raises(ValueError):
            validate_recommendation(**args)


def test_wait_and_mismatched_decision_cannot_recommend():
    for updates in ({"action": "WAIT"}, {"id": "other"}, {"model_version": "other"}):
        args = context()
        args["decision"] = changed(args["decision"], **updates)
        with pytest.raises(ValueError):
            validate_recommendation(**args)


def test_current_recommendation_cannot_use_later_archival_retrieval():
    args = context()
    args["evidence"] = (
        changed(args["evidence"][0], retrieved_at=AT + timedelta(days=1)),
    )
    with pytest.raises(ValueError):
        validate_recommendation(**args)


def test_notification_sent_requires_acknowledgement():
    fields = dict(id="attempt-1", recommendation_id="rec-1", recorded_at=AT)
    pending = NotificationAttempt(**fields, status="PENDING")
    assert pending.sent_at is None
    with pytest.raises(ValidationError):
        NotificationAttempt(**fields, status="SENT", attempted_at=AT)
    sent = NotificationAttempt(
        **fields,
        status="SENT",
        attempted_at=AT,
        sent_at=AT,
        provider_message_id="synthetic-1",
    )
    assert sent.sent_at == AT
    with pytest.raises(ValidationError):
        changed(sent, status="UNKNOWN")
    with pytest.raises(ValidationError):
        changed(sent, recorded_at=AT - timedelta(seconds=1))
