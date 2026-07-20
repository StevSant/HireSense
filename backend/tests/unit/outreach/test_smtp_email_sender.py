import smtplib
import ssl

import pytest

from hiresense.adapters import SmtpEmailSender
from hiresense.kernel import EmailMessage
from hiresense.ports import EmailUnavailableError


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
    with pytest.raises(EmailUnavailableError):  # blank host disables sending
        _sender(host="").send(EmailMessage(to="r@example.com", subject="Hi", body="Body"))


# --- #149: refuse plaintext credential auth; use an explicit SSLContext ---


def test_send_refuses_login_over_plaintext(monkeypatch):
    created = _install_fake_smtp(monkeypatch)

    with pytest.raises(EmailUnavailableError):
        _sender(use_tls=False, username="user", password="pw").send(
            EmailMessage(to="r@example.com", subject="Hi", body="Body")
        )

    assert created == []  # refused before any connection was opened


def test_send_allows_plaintext_auth_when_insecure_opt_in(monkeypatch):
    created = _install_fake_smtp(monkeypatch)

    _sender(use_tls=False, username="user", password="pw", allow_insecure=True).send(
        EmailMessage(to="r@example.com", subject="Hi", body="Body")
    )

    assert created[0].login_args == ("user", "pw")
    assert created[0].starttls_context == "NOT_CALLED"  # no TLS on this channel


def test_send_without_credentials_over_plaintext_is_allowed(monkeypatch):
    # mailhog-style dev server: no auth -> no credentials on the wire -> allowed.
    created = _install_fake_smtp(monkeypatch)

    _sender(use_tls=False, username="").send(
        EmailMessage(to="r@example.com", subject="Hi", body="Body")
    )

    assert created[0].login_args is None
    assert created[0].sent is not None


def test_send_uses_verified_ssl_context_by_default(monkeypatch):
    created = _install_fake_smtp(monkeypatch)

    _sender(use_tls=True).send(EmailMessage(to="r@example.com", subject="Hi", body="Body"))

    ctx = created[0].starttls_context
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_send_uses_unverified_ssl_context_when_insecure(monkeypatch):
    created = _install_fake_smtp(monkeypatch)

    _sender(use_tls=True, allow_insecure=True).send(
        EmailMessage(to="r@example.com", subject="Hi", body="Body")
    )

    ctx = created[0].starttls_context
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE
