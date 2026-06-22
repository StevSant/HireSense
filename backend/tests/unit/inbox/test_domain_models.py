from datetime import datetime, timezone

from hiresense.inbox.domain import (
    DetectedSignal,
    EmailClassification,
    EmailSignalKind,
    InboundEmail,
    SignalState,
)


def test_models_construct():
    email = InboundEmail(
        message_id="m1", from_address="r@acme.com", subject="Update",
        body="...", received_at=datetime.now(timezone.utc),
    )
    assert email.message_id == "m1"
    c = EmailClassification(job_related=True, kind=EmailSignalKind.REJECTION,
                            company="Acme", role="Dev", confidence=0.8)
    assert c.kind is EmailSignalKind.REJECTION
    sig = DetectedSignal(
        message_id="m1", from_address="r@acme.com", subject="Update",
        received_at=email.received_at, kind=EmailSignalKind.REJECTION,
        company="Acme", role="Dev", confidence=0.8,
        matched_application_id=None, proposed_status=None, state=SignalState.PENDING,
    )
    assert sig.state is SignalState.PENDING
    assert EmailSignalKind.OFFER.value == "offer"
    assert SignalState.DISMISSED.value == "dismissed"
