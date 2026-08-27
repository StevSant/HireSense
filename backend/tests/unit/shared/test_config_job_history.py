from __future__ import annotations

from hiresense.shared.config.groups.ingestion import IngestionSettings


def test_job_history_retention_defaults_to_90_days():
    assert IngestionSettings().job_history_retention_days == 90


def test_job_history_retention_can_be_disabled_with_zero():
    assert IngestionSettings(job_history_retention_days=0).job_history_retention_days == 0


def test_ingestion_listing_default_floor_is_40_percent():
    assert IngestionSettings.model_fields["ingestion_min_match_score"].default == 0.4
