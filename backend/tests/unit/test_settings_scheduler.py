from hiresense.config import Settings


def test_scheduler_settings_have_safe_defaults():
    s = Settings()
    # Master switch defaults OFF so `uv run app --reload` never double-fires.
    assert s.scheduler_enabled is False
    assert s.scheduler_run_retention_days == 30
