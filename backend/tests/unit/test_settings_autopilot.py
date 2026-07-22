from hiresense.config.groups import SchedulingSettings


def test_autopilot_pipeline_settings_defaults():
    fields = SchedulingSettings.model_fields

    # Read the declared defaults directly so a developer's backend/.env cannot
    # turn this unit test into an assertion about their local configuration.
    assert fields["autopilot_pipeline_enabled"].default is False
    assert fields["autopilot_pipeline_top_n"].default == 3
    assert fields["autopilot_pipeline_schedule"].default == "0 10 * * *"
    assert fields["autopilot_draft_concurrency"].default == 3
