"""Backward-compatible re-export. Import from kernel.events."""

from hiresense.kernel.events.jobs_ingested import JobsIngestedEvent

__all__ = ["JobsIngestedEvent"]
