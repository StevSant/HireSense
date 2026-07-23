import pytest
from pydantic import ValidationError

from hiresense.config.groups import IngestionSettings, SchedulingSettings


def _validated_retention_settings(
    settings_class: type[IngestionSettings] | type[SchedulingSettings],
    field_name: str,
    value: int,
    monkeypatch: pytest.MonkeyPatch,
) -> IngestionSettings | SchedulingSettings:
    # Pydantic's base environment source cannot parse HireSense's comma-separated
    # source list. The composed Settings class replaces it, but these narrow unit
    # tests validate each config group directly, so keep a developer's ambient
    # value out of the group-level test.
    monkeypatch.delenv("ENABLED_JOB_SOURCES", raising=False)
    return settings_class(**{field_name: value})


@pytest.mark.parametrize(
    ("settings_class", "field_name"),
    [
        (IngestionSettings, "ingestion_job_retention_days"),
        (SchedulingSettings, "autohunt_digest_retention_days"),
        (SchedulingSettings, "scheduler_run_retention_days"),
    ],
)
def test_retention_days_reject_values_outside_the_supported_window(
    settings_class: type[IngestionSettings] | type[SchedulingSettings],
    field_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for invalid_value in (-1, 3651):
        with pytest.raises(ValidationError):
            _validated_retention_settings(settings_class, field_name, invalid_value, monkeypatch)


@pytest.mark.parametrize(
    ("settings_class", "field_name"),
    [
        (IngestionSettings, "ingestion_job_retention_days"),
        (SchedulingSettings, "autohunt_digest_retention_days"),
        (SchedulingSettings, "scheduler_run_retention_days"),
    ],
)
def test_retention_days_allow_the_documented_disabled_and_maximum_values(
    settings_class: type[IngestionSettings] | type[SchedulingSettings],
    field_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        getattr(
            _validated_retention_settings(settings_class, field_name, 0, monkeypatch), field_name
        )
        == 0
    )
    assert (
        getattr(
            _validated_retention_settings(settings_class, field_name, 3650, monkeypatch), field_name
        )
        == 3650
    )
