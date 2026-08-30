import pytest
from pydantic import ValidationError

from hiresense.shared.config import Settings


def test_submission_defaults_are_safe():
    s = Settings(_env_file=None)
    assert s.autopilot_submit_enabled is False
    assert s.apply_agent_dry_run is True
    assert s.autopilot_submit_daily_cap == 10
    assert s.submission_confidence_threshold == 0.75
    assert s.submission_max_attempts == 2


def test_submission_thresholds_are_bounded():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, submission_confidence_threshold=1.5)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, autopilot_submit_daily_cap=-1)
