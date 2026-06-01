from __future__ import annotations

from hiresense.observability import get_domain_metrics


def test_domain_metrics_singleton_exposes_instruments():
    m1 = get_domain_metrics()
    m2 = get_domain_metrics()
    assert m1 is m2  # singleton
    # Instruments exist and recording does not raise (no-op meter is fine).
    m1.jobs_fetched_total.add(3, {"source": "remotive"})
    m1.jobs_scored_total.add(2, {"source": "remotive"})
    m1.ingestion_run_duration_ms.record(120.5, {"source": "remotive"})
    m1.matches_completed_total.add(1)
    m1.match_score.record(0.82)
    m1.llm_tokens_total.add(50, {"type": "input"})
    m1.llm_cost_usd_total.add(0.001)
    m1.llm_call_duration_ms.record(900.0, {"model": "claude-haiku-4-5"})
    m1.llm_errors_total.add(0)
    m1.events_published_total.add(1, {"type": "jobs_ingested"})
    m1.event_handler_errors_total.add(0, {"type": "jobs_ingested"})
