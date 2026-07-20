import smtplib

import pytest

from hiresense.adapters import SmtpEmailSender
from hiresense.kernel import EmailMessage


class _FakeSMTP:
    """Records constructor/handshake calls; used as a context manager."""

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.starttls_context = "NOT_CALLED"
        self.login_args = None
        self.sent = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, *, context=None):
        self.starttls_context = context

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, msg, to_addrs=None):
        self.sent = {
            "to_header": msg["To"],
            "subject": msg["Subject"],
            "to_addrs": to_addrs,
        }


def _install_fake_smtp(monkeypatch):
    created: list[_FakeSMTP] = []

    def factory(host, port, timeout=None):
        fake = _FakeSMTP(host, port, timeout=timeout)
        created.append(fake)
        return fake

    monkeypatch.setattr(smtplib, "SMTP", factory)
    return created


def _sender(**overrides) -> SmtpEmailSender:
    kwargs = dict(
        host="smtp.example.com",
        port=587,
        username="",
        password="",
        from_email="me@example.com",
        use_tls=True,
        timeout=30.0,
    )
    kwargs.update(overrides)
    return SmtpEmailSender(**kwargs)


def test_send_passes_timeout_to_smtp(monkeypatch):
    created = _install_fake_smtp(monkeypatch)

    _sender(timeout=12.5).send(EmailMessage(to="r@example.com", subject="Hi", body="Body"))

    assert created[0].timeout == 12.5


def test_send_raises_when_not_configured():
    with pytest.raises(Exception):  # EmailUnavailableError; blank host disables sending
        _sender(host="").send(EmailMessage(to="r@example.com", subject="Hi", body="Body"))
