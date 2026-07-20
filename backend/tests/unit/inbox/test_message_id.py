from datetime import datetime, timezone

from hiresense.inbox.domain import synthesize_message_id


def _args(**overrides):
    base = dict(
        from_address="recruiter@acme.com",
        subject="Your application",
        received_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
        body="We would like to schedule an interview.",
    )
    base.update(overrides)
    return base


def test_synthesized_id_is_prefixed_and_stable():
    first = synthesize_message_id(**_args())
    second = synthesize_message_id(**_args())
    assert first == second
    assert first.startswith("synthesized:")


def test_distinct_content_yields_distinct_ids():
    base = synthesize_message_id(**_args())
    assert synthesize_message_id(**_args(from_address="other@acme.com")) != base
    assert synthesize_message_id(**_args(subject="Different")) != base
    assert synthesize_message_id(**_args(body="Different body")) != base
    assert (
        synthesize_message_id(**_args(received_at=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)))
        != base
    )
