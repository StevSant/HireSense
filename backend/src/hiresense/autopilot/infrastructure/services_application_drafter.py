from __future__ import annotations

import logging
import uuid as uuid_mod
from typing import Any

from hiresense.autopilot.domain import DraftStatus

logger = logging.getLogger(__name__)


class ServicesApplicationDrafter:
    """Drives the existing applications services to create an application and
    generate its draft artifacts. Maps failures to PARTIAL/FAILED rather than
    raising: a create failure -> FAILED (no application); a later artifact failure
    -> PARTIAL (application + whatever generated is kept)."""

    def __init__(
        self,
        *,
        application_service: Any,
        artifact_service: Any,
        apply_service: Any,
        cv_language: str,
    ) -> None:
        self._applications = application_service
        self._artifacts = artifact_service
        self._apply = apply_service
        self._cv_language = cv_language

    async def draft(
        self, job_id: str
    ) -> tuple[uuid_mod.UUID | None, DraftStatus, str | None]:
        try:
            aggregate = await self._applications.create_from_ingested(job_id)
        except Exception as exc:  # noqa: BLE001
            return None, DraftStatus.FAILED, str(exc)

        application_id = aggregate.id
        try:
            match = await self._artifacts.generate_match(
                application_id, cv_language=self._cv_language
            )
            await self._artifacts.generate_optimization(
                application_id, cv_language=self._cv_language, match_id=match.id
            )
            await self._apply.generate_cover_letter(
                application_id, cv_language=self._cv_language, tone=None
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("autopilot: artifact generation failed for job %r", job_id)
            return application_id, DraftStatus.PARTIAL, str(exc)

        return application_id, DraftStatus.DRAFTED, None
