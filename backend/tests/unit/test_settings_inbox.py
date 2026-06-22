from hiresense.config import Settings


def test_inbox_settings_defaults():
    s = Settings()
    assert s.imap_host == ""
    assert s.imap_port == 993
    assert s.imap_folder == "INBOX"
    assert s.imap_use_ssl is True
    assert s.inbox_scan_schedule == "0 */2 * * *"
    assert s.inbox_signal_match_min_confidence == 0.5
