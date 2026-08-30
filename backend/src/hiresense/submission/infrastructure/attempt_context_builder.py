from __future__ import annotations

import logging
from typing import Any

from hiresense.profile.domain import build_prefill
from hiresense.submission.domain import AgentContext

logger = logging.getLogger(__name__)


class AttemptContextBuilder:
    """Assembles the grounding material for one attempt, server-side.

    The runner never sees the candidate's profile or claims -- it only ships a
    page snapshot and receives an action. Everything an answer may be grounded
    in is gathered here, which keeps PII out of the runner process and makes
    the grounding rule enforceable in one place.
    """

    def __init__(
        self,
        *,
        profile_service: Any,
        claim_service: Any = None,
        job_query: Any = None,
    ) -> None:
        self._profiles = profile_service
        self._claims = claim_service
        self._jobs = job_query

    async def build(self, attempt: Any) -> AgentContext:
        profile = await self._profiles.get_current_profile()
        prefill = build_prefill(profile) if profile is not None else {}

        screening: list[tuple[str, str]] = []
        if profile is not None and profile.apply_profile is not None:
            screening = [(a.question, a.answer) for a in profile.apply_profile.screening_answers]

        claim_texts: list[str] = []
        if self._claims is not None:
            try:
                claim_texts = [c.text for c in self._claims.list_verified_for_readiness()]
            except Exception:  # noqa: BLE001 - missing claims must not block a run
                logger.exception("submission: could not load verified claims")

        job_text = ""
        if self._jobs is not None:
            try:
                job = self._jobs.get_job_by_id(attempt.job_id)
                job_text = getattr(job, "description", "") or "" if job is not None else ""
            except Exception:  # noqa: BLE001 - a missing job must not block the run
                logger.exception("submission: could not load job %r", attempt.job_id)

        return AgentContext(
            prefill=prefill,
            claim_texts=claim_texts,
            screening_answers=screening,
            job_text=job_text,
            needs_cv_upload=True,
            needs_letter_upload=True,
        )
