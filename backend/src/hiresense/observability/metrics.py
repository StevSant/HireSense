from __future__ import annotations

from hiresense.observability.meter import get_meter


class DomainMetrics:
    """Holds the hand-rolled business metric instruments. Created lazily so
    import never forces a MeterProvider."""

    def __init__(self) -> None:
        meter = get_meter("hiresense.domain")

        self.jobs_fetched_total = meter.create_counter(
            "hiresense.jobs_fetched_total",
            unit="1",
            description="Jobs fetched per ingestion source",
        )
        self.jobs_indexed_total = meter.create_counter(
            "hiresense.jobs_indexed_total",
            unit="1",
            description="Jobs queued for indexing (inserted/updated/reopened) per ingestion source",
        )
        self.ingestion_run_duration_ms = meter.create_histogram(
            "hiresense.ingestion_run_duration_ms",
            unit="ms",
            description="Wall-clock duration of an ingestion run",
        )
        self.matches_completed_total = meter.create_counter(
            "hiresense.matches_completed_total",
            unit="1",
            description="Match evaluations completed",
        )
        self.match_score = meter.create_histogram(
            "hiresense.match_score",
            unit="1",
            description="Distribution of computed match scores",
        )
        self.llm_tokens_total = meter.create_counter(
            "hiresense.llm_tokens_total",
            unit="1",
            description="LLM tokens consumed (type=input|output)",
        )
        self.llm_cost_usd_total = meter.create_counter(
            "hiresense.llm_cost_usd_total",
            unit="{USD}",
            description="Estimated LLM spend",
        )
        self.llm_call_duration_ms = meter.create_histogram(
            "hiresense.llm_call_duration_ms",
            unit="ms",
            description="LLM call latency",
        )
        self.llm_errors_total = meter.create_counter(
            "hiresense.llm_errors_total",
            unit="1",
            description="Failed LLM calls",
        )
        self.events_published_total = meter.create_counter(
            "hiresense.events_published_total",
            unit="1",
            description="Domain events published",
        )
        self.event_handler_errors_total = meter.create_counter(
            "hiresense.event_handler_errors_total",
            unit="1",
            description="Domain event handler failures",
        )
        self.automation_failures_total = meter.create_counter(
            "hiresense.automation_failures_total",
            unit="1",
            description=(
                "Swallowed failures in background automation (log-and-continue paths). "
                "Attribute component=scheduler_job|inbox_fetch|autohunt_rerank|"
                "autohunt_prune|autopilot_draft"
            ),
        )
        self.embedding_encode_duration_ms = meter.create_histogram(
            "hiresense.embedding_encode_duration_ms",
            unit="ms",
            description="Sentence-transformer encode() latency (queue + execution)",
        )
        self.source_fetch_duration_ms = meter.create_histogram(
            "hiresense.source_fetch_duration_ms",
            unit="ms",
            description="Per-source job fetch duration during an ingestion run",
        )


_INSTANCE: DomainMetrics | None = None


def get_domain_metrics() -> DomainMetrics:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = DomainMetrics()
    return _INSTANCE
