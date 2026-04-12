"""Backward-compatible re-export. Import from kernel.schemas or kernel.events."""

from hiresense.kernel.events.jobs_ingested import JobsIngestedEvent
from hiresense.kernel.schemas.normalized_job_dto import NormalizedJobDTO

__all__ = ["JobsIngestedEvent", "NormalizedJobDTO"]
