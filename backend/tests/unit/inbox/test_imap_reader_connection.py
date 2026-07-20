import imaplib

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


def test_fetch_passes_timeout_to_imap(monkeypatch):
    created = _install_fake_imap_ssl(monkeypatch)

    assert _reader(timeout=17.5).fetch_unseen() == []
    assert created[0].timeout == 17.5
