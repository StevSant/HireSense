import pytest

from hiresense.notifications.domain import NotificationService, render_pipeline_drafts_email


class _Sender:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


def test_render_includes_count():
    subject, body = render_pipeline_drafts_email(3)
    assert "3" in subject
    assert "3" in body


@pytest.mark.asyncio
async def test_notify_sends_when_enabled():
    sender = _Sender()
    assert (
        await NotificationService(sender=sender, to_email="me@x.com").notify_pipeline_drafts(2)
        is True
    )
    assert len(sender.sent) == 1


@pytest.mark.asyncio
async def test_notify_noop_when_disabled():
    sender = _Sender()
    assert await NotificationService(sender=sender, to_email="").notify_pipeline_drafts(2) is False
    assert sender.sent == []
