from datetime import datetime, timezone

import pytest

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.notifications.domain import NotificationService
from hiresense.ports import EmailUnavailableError


class _Sender:
    def __init__(self, raise_exc=None):
        self.sent = []
        self._raise = raise_exc

    def send(self, message):
        if self._raise is not None:
            raise self._raise
        self.sent.append(message)


def _digest():
    return Digest(
        cutoff_at=datetime.now(timezone.utc),
        job_count=1,
        entries=[DigestEntry(job_id="1", title="Dev", company="Acme", url=None, score=0.9)],
    )


@pytest.mark.asyncio
async def test_disabled_when_recipient_blank_is_noop():
    sender = _Sender()
    svc = NotificationService(sender=sender, to_email="")
    assert svc.enabled is False
    assert await svc.notify_new_matches(_digest()) is False
    assert await svc.notify_job_failure("ingestion_fetch", "boom") is False
    assert sender.sent == []


@pytest.mark.asyncio
async def test_enabled_sends_to_recipient():
    sender = _Sender()
    svc = NotificationService(sender=sender, to_email="me@x.com")
    assert await svc.notify_new_matches(_digest()) is True
    assert len(sender.sent) == 1
    assert sender.sent[0].to == "me@x.com"
    assert "new job match" in sender.sent[0].subject


@pytest.mark.asyncio
async def test_send_error_on_digest_path_is_swallowed():
    sender = _Sender(raise_exc=EmailUnavailableError("smtp down"))
    svc = NotificationService(sender=sender, to_email="me@x.com")
    assert await svc.notify_new_matches(_digest()) is False  # no raise


@pytest.mark.asyncio
async def test_send_test_raises_when_disabled():
    svc = NotificationService(sender=_Sender(), to_email="")
    with pytest.raises(EmailUnavailableError):
        await svc.send_test()
