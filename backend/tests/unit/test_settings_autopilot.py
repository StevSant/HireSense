from hiresense.config import Settings


def test_autopilot_pipeline_settings_defaults():
    s = Settings()
    assert s.autopilot_pipeline_enabled is False
    assert s.autopilot_pipeline_top_n == 3
    assert s.autopilot_pipeline_schedule == "0 10 * * *"
