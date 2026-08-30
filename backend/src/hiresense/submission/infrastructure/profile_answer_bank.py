from __future__ import annotations

import logging
from typing import Any

from hiresense.profile.domain import ApplyProfile, ScreeningAnswer

logger = logging.getLogger(__name__)


class ProfileAnswerBank:
    """Persists human-supplied answers onto the candidate's ApplyProfile.

    Reuses the screening-answer bank that already backs Apply Assist, so an
    answer the candidate gives once to unblock an escalation is immediately
    available to every later application -- including the manual userscript
    path. This is what makes the escalation queue drain over time.
    """

    def __init__(self, profile_service: Any) -> None:
        self._profiles = profile_service

    async def remember(self, answers: list[tuple[str, str]]) -> None:
        if not answers:
            return
        profile = await self._profiles.get_current_profile()
        if profile is None:
            logger.info("submission: no profile yet, cannot store resumed answers")
            return

        apply_profile = profile.apply_profile or ApplyProfile()
        existing = list(apply_profile.screening_answers)
        by_question = {a.question.casefold(): i for i, a in enumerate(existing)}

        for question, answer in answers:
            key = question.casefold()
            entry = ScreeningAnswer(question=question, answer=answer)
            if key in by_question:
                existing[by_question[key]] = entry
            else:
                by_question[key] = len(existing)
                existing.append(entry)

        await self._profiles.set_apply_profile(
            apply_profile.model_copy(update={"screening_answers": existing})
        )
