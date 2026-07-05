from pydantic_settings import BaseSettings


class SchedulingSettings(BaseSettings):
    """Auto-hunt digest, autopilot pipeline, and in-app scheduler settings."""

    # --- Proactive Auto-Hunt (scheduled digest of new taste-ranked matches) ---
    # Top-N new matches per digest, and the minimum match score (0-1) to qualify.
    autohunt_top_n: int = 5
    autohunt_min_score: float = 0.6
    # First-run lookback window (no prior digest to anchor the watermark).
    autohunt_initial_lookback_days: int = 7
    # Digests older than this are pruned at the end of each run.
    autohunt_digest_retention_days: int = 90
    # Intended cron cadence — INFORMATIONAL ONLY; the app never self-schedules.
    autohunt_schedule: str = "0 9 * * *"

    # --- Autopilot pipeline (Phase 4: auto-draft applications for top matches) ---
    # Gates the autopilot_pipeline scheduler job entirely. Default OFF (auto-drafting
    # CVs/cover letters is LLM-heavy — opt in deliberately).
    autopilot_pipeline_enabled: bool = False
    # Max digest entries to draft per run (bounds LLM spend).
    autopilot_pipeline_top_n: int = 3
    # Cron for the autopilot_pipeline job (after autohunt's 0 9 * * * so a digest exists).
    autopilot_pipeline_schedule: str = "0 10 * * *"

    # --- Scheduler (in-app cadence driver; Autopilot Phase 1) ---
    # Master switch. MUST be true on exactly one process (the app self-drives
    # ingestion/revalidation/autohunt/outreach-followups on the cron strings
    # already defined above). Default OFF so `uv run app --reload` in dev does
    # not double-fire; docker-compose sets it true for the `app` service.
    scheduler_enabled: bool = False
    # Prune scheduler_job_runs rows older than this (inline on each insert).
    scheduler_run_retention_days: int = 30
