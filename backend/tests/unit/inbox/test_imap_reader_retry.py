from __future__ import annotations

import imaplib

from hiresense.inbox.infrastructure import ImapInboxReader

_SLEEP = "hiresense.inbox.infrastructure.imap_inbox_reader.time.sleep"
_METRICS = "hiresense.inbox.infrastructure.imap_inbox_reader.get_domain_metrics"


class _Counter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict]] = []

    def add(self, value, attributes=None) -> None:
        self.calls.append((value, attributes or {}))


class _Metrics:
    def __init__(self) -> None:
        self.automation_failures_total = _Counter()


def _reader(max_retries: int = 2) -> ImapInboxReader:
    return ImapInboxReader(
        host="imap.example.com",
        port=993,
        username="u",
        password="p",
        folder="INBOX",
        use_ssl=True,
        max_retries=max_retries,
        retry_base_delay=0.01,
    )


def test_transient_error_is_retried_then_succeeds(monkeypatch) -> None:
    reader = _reader(max_retries=2)
    attempts = {"n": 0}

    def fake_fetch():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OSError("connection reset")
        return ["email"]

    monkeypatch.setattr(reader, "_fetch", fake_fetch)
    sleeps: list[float] = []
    monkeypatch.setattr(_SLEEP, lambda d: sleeps.append(d))

    result = reader.fetch_unseen()

    assert result == ["email"]
    assert attempts["n"] == 2  # failed once, retried once
    assert len(sleeps) == 1


def test_transient_error_exhausts_retries_and_records_metric(monkeypatch) -> None:
    reader = _reader(max_retries=2)
    attempts = {"n": 0}

    def fake_fetch():
        attempts["n"] += 1
        raise OSError("still down")

    monkeypatch.setattr(reader, "_fetch", fake_fetch)
    monkeypatch.setattr(_SLEEP, lambda d: None)
    metrics = _Metrics()
    monkeypatch.setattr(_METRICS, lambda: metrics)

    result = reader.fetch_unseen()

    assert result == []
    assert attempts["n"] == 3  # 1 initial + 2 retries
    assert len(metrics.automation_failures_total.calls) == 1
    _, attrs = metrics.automation_failures_total.calls[0]
    assert attrs.get("component") == "inbox_fetch"


def test_non_transient_error_is_not_retried(monkeypatch) -> None:
    # A protocol/auth error (IMAP4.error, not abort) is permanent — no retry.
    reader = _reader(max_retries=2)
    attempts = {"n": 0}

    def fake_fetch():
        attempts["n"] += 1
        raise imaplib.IMAP4.error("authentication failed")

    monkeypatch.setattr(reader, "_fetch", fake_fetch)
    slept: list[float] = []
    monkeypatch.setattr(_SLEEP, lambda d: slept.append(d))
    metrics = _Metrics()
    monkeypatch.setattr(_METRICS, lambda: metrics)

    result = reader.fetch_unseen()

    assert result == []
    assert attempts["n"] == 1  # no retry on a permanent error
    assert slept == []
    assert len(metrics.automation_failures_total.calls) == 1
