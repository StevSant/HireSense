from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class SubmissionSettings(BaseSettings):
    """Auto-apply agent: the outbound submission queue and its local runner."""

    # --- Master switch (Autopilot Phase 5) ---
    # Gates the entire outbound path. Default OFF: this submits applications to
    # real employers under the candidate's name -- it is opted into deliberately.
    autopilot_submit_enabled: bool = False
    # Match score (0-1) a draft must clear before its packet is machine-approved.
    autopilot_submit_min_score: float = Field(default=0.75, ge=0.0, le=1.0)
    # Attempts enqueued per calendar day. Bounds the blast radius of a bad batch.
    autopilot_submit_daily_cap: int = Field(default=10, ge=0, le=500)

    # --- The confidence gate ---
    # Minimum per-field confidence across all REQUIRED fields for the agent to
    # submit unattended. Below this the attempt escalates to the review queue.
    submission_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    # Retries after a runner lease expires (crash / kill), per attempt.
    submission_max_attempts: int = Field(default=2, ge=1, le=10)
    # How long a runner holds a claimed attempt before it returns to the queue.
    submission_lease_seconds: int = Field(default=300, ge=30, le=3600)

    # --- The local runner (`uv run apply-agent`) ---
    # Chrome DevTools Protocol endpoint of the candidate's own browser. Start
    # Chrome with --remote-debugging-port=9222 to expose it.
    apply_agent_cdp_url: str = "http://localhost:9222"
    # Backend base URL the runner calls back into.
    apply_agent_api_base: str = "http://localhost:8000"
    # Bearer token the runner authenticates with (same identity tokens as the UI).
    apply_agent_api_token: SecretStr = SecretStr("")
    # Hard ceiling on agent steps per attempt, so a loop on a broken form ends.
    apply_agent_max_steps: int = Field(default=25, ge=1, le=200)
    # Dry run: fill everything, capture evidence, but DO NOT click submit.
    # Ships ON. Turn off only after reviewing the audit tape of a few real runs.
    apply_agent_dry_run: bool = True
