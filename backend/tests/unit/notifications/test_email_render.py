from datetime import datetime, timezone

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.notifications.domain import render_digest_email, render_job_failure_email


def _digest():
    return Digest(
        cutoff_at=datetime.now(timezone.utc),
        job_count=2,
        entries=[
            DigestEntry(
                job_id="1", title="Senior Python Dev", company="Acme", url="http://x/1", score=0.91
            ),
            DigestEntry(
                job_id="2", title="Backend Engineer", company="Globex", url=None, score=0.84
            ),
        ],
    )


def test_digest_email_lists_each_match():
    subject, body = render_digest_email(_digest())
    assert "2" in subject  # match count in the subject
    assert "Senior Python Dev" in body
    assert "Acme" in body
    assert "Backend Engineer" in body
    assert "Globex" in body
    assert "http://x/1" in body  # link present when url is set


def test_job_failure_email_includes_name_and_detail():
    subject, body = render_job_failure_email("ingestion_fetch", "connection refused")
    assert "ingestion_fetch" in subject or "ingestion_fetch" in body
    assert "connection refused" in body
