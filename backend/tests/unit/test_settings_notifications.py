from hiresense.config import Settings


def test_notification_settings_default_blank():
    s = Settings()
    assert s.notification_email == ""
    assert s.notification_from_email == ""
