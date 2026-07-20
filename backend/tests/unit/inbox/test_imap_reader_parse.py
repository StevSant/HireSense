from hiresense.inbox.infrastructure import ImapInboxReader


def _raw(subject: str, body: str, message_id: str | None = None) -> bytes:
    headers = [
        "From: recruiter@acme.com",
        f"Subject: {subject}",
        "Date: Sat, 05 Jul 2026 12:00:00 +0000",
    ]
    if message_id is not None:
        headers.append(f"Message-ID: {message_id}")
    return ("\r\n".join(headers) + "\r\n\r\n" + body).encode("utf-8")


def test_parse_keeps_real_message_id():
    parsed = ImapInboxReader._parse(_raw("Hi", "body", message_id="<abc@acme.com>"))
    assert parsed is not None
    assert parsed.message_id == "<abc@acme.com>"


def test_header_less_emails_get_distinct_stable_ids():
    """Two different header-less emails must not collapse onto one dedup key,
    and the same email re-parsed keeps the same key (issue #150)."""
    first = ImapInboxReader._parse(_raw("Rejection", "We regret to inform you"))
    second = ImapInboxReader._parse(_raw("Interview", "Please pick a slot"))
    first_again = ImapInboxReader._parse(_raw("Rejection", "We regret to inform you"))

    assert first is not None and second is not None
    # Neither collapses onto the old empty-string key.
    assert first.message_id != ""
    assert second.message_id != ""
    # Distinct content -> distinct keys; identical content -> identical key.
    assert first.message_id != second.message_id
    assert first.message_id == first_again.message_id
