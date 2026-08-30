from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable

from hiresense.submission.domain.agent_action import (
    AgentAction,
    EscalateAction,
    FillFieldsAction,
    SubmitAction,
    UploadFileAction,
)
from hiresense.submission.domain.agent_context import AgentContext
from hiresense.submission.domain.answer_source import AnswerSource
from hiresense.submission.domain.page_observation import PageObservation
from hiresense.submission.domain.ports.answer_bank_port import AnswerBankPort
from hiresense.submission.domain.ports.submission_repository import SubmissionRepository
from hiresense.submission.domain.submission_attempt import SubmissionAttempt
from hiresense.submission.domain.submission_event import SubmissionEvent
from hiresense.submission.domain.submission_event_kind import SubmissionEventKind
from hiresense.submission.domain.submission_status import SubmissionStatus

logger = logging.getLogger(__name__)

# Canonical keys whose values are personal data. Their values are recorded on
# the audit tape as a hash; free-text answers are recorded verbatim, because
# those are the sentences that went out under the candidate's name.
_PII_KEYS = frozenset(
    {
        "full_name",
        "first_name",
        "last_name",
        "preferred_name",
        "email",
        "phone",
        "location",
        "linkedin_url",
        "github_url",
        "portfolio_url",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day(now: datetime) -> datetime:
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def _redact(canonical_key: str | None, value: str) -> str:
    if canonical_key in _PII_KEYS:
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return value


class SubmissionService:
    """Owns the lifecycle of every submission attempt.

    All external side effects flow through here, which is what makes the
    outbound path bounded: the daily cap and the duplicate guard are enforced
    at enqueue time, and every agent decision is written to an append-only
    audit tape before it is acted on.
    """

    def __init__(
        self,
        repo: SubmissionRepository,
        agent: Any,
        answer_bank: AnswerBankPort,
        *,
        daily_cap: int,
        lease_seconds: int,
        max_attempts: int,
        clock: Callable[[], datetime] = _utcnow,
        notifier: Any | None = None,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._bank = answer_bank
        self._daily_cap = daily_cap
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._clock = clock
        self._notifier = notifier

    # --- inbound -----------------------------------------------------------

    def enqueue(
        self,
        *,
        application_id: uuid.UUID,
        job_id: str,
        packet_id: uuid.UUID | None,
        channel: str,
        target_url: str,
    ) -> SubmissionAttempt | None:
        """Queue one application for submission.

        Returns None -- never raises -- when the daily cap is exhausted or the
        application already has a live attempt. Callers treat that as "not
        today", not as an error.
        """
        if self._daily_cap <= 0:
            logger.info("submission: daily cap is 0, refusing to enqueue %s", application_id)
            return None
        now = self._clock()
        if self._repo.count_created_since(_start_of_day(now)) >= self._daily_cap:
            logger.info("submission: daily cap %d reached, skipping %s", self._daily_cap, job_id)
            return None
        if self._repo.has_live_attempt(application_id):
            logger.info("submission: %s already has a live attempt, skipping", application_id)
            return None
        return self._repo.create(
            SubmissionAttempt(
                application_id=application_id,
                job_id=job_id,
                packet_id=packet_id,
                channel=channel,
                target_url=target_url,
            )
        )

    def lease(self, runner_id: str, capacity: int) -> list[SubmissionAttempt]:
        return self._repo.lease(
            runner_id=runner_id,
            capacity=capacity,
            lease_seconds=self._lease_seconds,
            now=self._clock(),
        )

    def heartbeat(self, attempt_id: uuid.UUID) -> SubmissionAttempt | None:
        attempt = self._repo.get(attempt_id)
        if attempt is None:
            return None
        now = self._clock()
        return self._repo.update(
            attempt.model_copy(
                update={"lease_expires_at": now + timedelta(seconds=self._lease_seconds)}
            )
        )

    # --- the agent loop ----------------------------------------------------

    async def observe(
        self,
        attempt_id: uuid.UUID,
        observation: PageObservation,
        context: AgentContext,
    ) -> AgentAction:
        """Ask the agent for the next action and record it on the audit tape."""
        attempt = await asyncio.to_thread(self._repo.get, attempt_id)
        if attempt is None:
            raise ValueError(f"Submission attempt {attempt_id} not found")

        if attempt.status is SubmissionStatus.CLAIMED:
            attempt = await asyncio.to_thread(
                self._repo.update,
                attempt.model_copy(update={"status": SubmissionStatus.IN_PROGRESS}),
            )

        action = await self._agent.next_action(observation=observation, context=context)
        await asyncio.to_thread(self._record, attempt_id, action)

        if isinstance(action, EscalateAction):
            escalated = await asyncio.to_thread(
                self._repo.update,
                attempt.model_copy(
                    update={
                        "status": SubmissionStatus.ESCALATED,
                        "escalation_reason": action.reason,
                        "escalated_fields": list(action.fields),
                        "finished_at": self._clock(),
                    }
                ),
            )
            if self._notifier is not None:
                try:
                    await self._notifier.notify_submission_escalations([escalated])
                except Exception:  # noqa: BLE001 - notification is best-effort
                    logger.exception("submission: escalation notification failed")
        return action

    def _record(self, attempt_id: uuid.UUID, action: AgentAction) -> None:
        kind, payload = self._describe(action)
        self._repo.append_event(
            SubmissionEvent(
                attempt_id=attempt_id,
                seq=self._repo.next_seq(attempt_id),
                kind=kind,
                payload=payload,
            )
        )

    @staticmethod
    def _describe(action: AgentAction) -> tuple[SubmissionEventKind, dict[str, Any]]:
        if isinstance(action, FillFieldsAction):
            return SubmissionEventKind.FILL, {
                "fills": [
                    {
                        "selector": f.selector,
                        "canonical_key": f.canonical_key,
                        "value": _redact(f.canonical_key, f.value),
                        "confidence": f.confidence,
                        "source": f.source.value,
                        "rationale": f.rationale,
                        "generated": f.source is AnswerSource.LLM,
                    }
                    for f in action.fills
                ]
            }
        if isinstance(action, EscalateAction):
            return SubmissionEventKind.ESCALATE, {
                "reason": action.reason,
                "fields": list(action.fields),
            }
        if isinstance(action, SubmitAction):
            return SubmissionEventKind.SUBMIT, {
                "selector": action.selector,
                "dry_run": action.dry_run,
            }
        if isinstance(action, UploadFileAction):
            return SubmissionEventKind.UPLOAD, {
                "selector": action.selector,
                "artifact": action.artifact,
            }
        return SubmissionEventKind.NAVIGATE, action.model_dump(mode="json")

    # --- terminal transitions ---------------------------------------------

    def complete(
        self,
        attempt_id: uuid.UUID,
        *,
        status: SubmissionStatus,
        evidence: dict[str, Any] | None = None,
    ) -> SubmissionAttempt:
        attempt = self._require(attempt_id)
        return self._repo.update(
            attempt.model_copy(
                update={
                    "status": status,
                    "evidence": dict(evidence or {}),
                    "finished_at": self._clock(),
                    "lease_expires_at": None,
                }
            )
        )

    async def resume(self, attempt_id: uuid.UUID, answers: dict[str, str]) -> SubmissionAttempt:
        """Take the human's answers, teach them to the answer bank, re-queue.

        The write-back is the point: the same question must not escalate twice.
        """
        attempt = self._require(attempt_id)
        pairs = [(q, a) for q, a in answers.items() if a and a.strip()]
        if pairs:
            try:
                await self._bank.remember(pairs)
            except Exception:  # noqa: BLE001 - a failed write-back must not block the retry
                logger.exception("submission: could not persist resumed answers")
        return self._repo.update(
            attempt.model_copy(
                update={
                    "status": SubmissionStatus.QUEUED,
                    "escalation_reason": None,
                    "escalated_fields": [],
                    "runner_id": None,
                    "claimed_at": None,
                    "lease_expires_at": None,
                    "finished_at": None,
                }
            )
        )

    def abandon(self, attempt_id: uuid.UUID) -> SubmissionAttempt:
        attempt = self._require(attempt_id)
        return self._repo.update(
            attempt.model_copy(
                update={
                    "status": SubmissionStatus.ABANDONED,
                    "finished_at": self._clock(),
                    "lease_expires_at": None,
                }
            )
        )

    def sweep_expired(self) -> int:
        return self._repo.expire_leases(self._clock(), self._max_attempts)

    def _require(self, attempt_id: uuid.UUID) -> SubmissionAttempt:
        attempt = self._repo.get(attempt_id)
        if attempt is None:
            raise ValueError(f"Submission attempt {attempt_id} not found")
        return attempt
