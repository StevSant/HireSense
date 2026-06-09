"""HireSense - AI-powered job matching and CV optimization."""

from hiresense.ingestion.ports.jobs_repository import (
    JobsRepositoryPort,
    QualityUpdate,
    ScoreUpdate,
    UpsertOutcome,
)

__all__ = ["JobsRepositoryPort", "QualityUpdate", "ScoreUpdate", "UpsertOutcome"]
