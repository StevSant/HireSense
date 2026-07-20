import imaplib
import ssl

from hiresense.inbox.infrastructure import ImapInboxReader


class _FakeIMAP:
    """Minimal IMAP client stub; returns no messages so _fetch completes cleanly."""

    def __init__(self, host, port, ssl_context=None, timeout=None):
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.timeout = timeout

    def login(self, username, password):
        return ("OK", [b"logged in"])

    def select(self, folder):
        return ("OK", [b"0"])

    def search(self, charset, criteria):
        return ("OK", [b""])

    def logout(self):
        return ("BYE", [b"bye"])


def _install_fake_imap_ssl(monkeypatch):
    created: list[_FakeIMAP] = []

    def factory(host, port, ssl_context=None, timeout=None):
        fake = _FakeIMAP(host, port, ssl_context=ssl_context, timeout=timeout)
        created.append(fake)
        return fake

    monkeypatch.setattr(imaplib, "IMAP4_SSL", factory)
    return created


def _reader(**overrides) -> ImapInboxReader:
    kwargs = dict(
        host="imap.example.com",
        port=993,
        username="user@example.com",
        password="secret",
        folder="INBOX",
        use_ssl=True,
        timeout=30.0,
    )
    kwargs.update(overrides)
    return ImapInboxReader(**kwargs)


def _install_fake_imap_plain(monkeypatch):
    created: list[_FakeIMAP] = []

    def factory(host, port, timeout=None):
        fake = _FakeIMAP(host, port, timeout=timeout)
        created.append(fake)
        return fake

    monkeypatch.setattr(imaplib, "IMAP4", factory)
    return created


def test_fetch_passes_timeout_to_imap(monkeypatch):
    created = _install_fake_imap_ssl(monkeypatch)

    assert _reader(timeout=17.5).fetch_unseen() == []
    assert created[0].timeout == 17.5


# --- #149: refuse plaintext credential auth; use an explicit SSLContext ---


def test_fetch_refuses_login_over_plaintext(monkeypatch):
    created = _install_fake_imap_plain(monkeypatch)

    assert _reader(use_ssl=False).fetch_unseen() == []  # refused, no-op scan
    assert created == []  # no connection opened


def test_fetch_uses_verified_ssl_context_by_default(monkeypatch):
    created = _install_fake_imap_ssl(monkeypatch)

    assert _reader(use_ssl=True).fetch_unseen() == []
    ctx = created[0].ssl_context
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_fetch_uses_unverified_ssl_context_when_insecure(monkeypatch):
    created = _install_fake_imap_ssl(monkeypatch)

    assert _reader(use_ssl=True, allow_insecure=True).fetch_unseen() == []
    ctx = created[0].ssl_context
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE
