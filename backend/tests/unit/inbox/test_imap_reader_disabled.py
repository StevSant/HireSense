from hiresense.inbox.infrastructure import ImapInboxReader


def test_blank_host_returns_empty():
    reader = ImapInboxReader(
        host="",
        port=993,
        username="",
        password="",
        folder="INBOX",
        use_ssl=True,
    )
    assert reader.fetch_unseen() == []
