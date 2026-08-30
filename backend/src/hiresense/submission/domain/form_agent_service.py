from __future__ import annotations

import logging

from hiresense.applications.domain import match_canonical_key
from hiresense.submission.domain.agent_action import (
    AgentAction,
    EscalateAction,
    FillFieldsAction,
    SubmitAction,
    UploadFileAction,
)
from hiresense.submission.domain.agent_context import AgentContext
from hiresense.submission.domain.answer_source import AnswerSource
from hiresense.submission.domain.field_answer import FieldAnswer
from hiresense.submission.domain.form_field import FormField
from hiresense.submission.domain.grounding import enforce_grounding
from hiresense.submission.domain.page_observation import PageObservation
from hiresense.submission.domain.ports.form_answer_port import FormAnswerPort

logger = logging.getLogger(__name__)

# Label fragments that identify the two document uploads every ATS asks for.
_CV_LABEL_HINTS = ("resume", "cv", "curriculum")
_LETTER_LABEL_HINTS = ("cover letter", "covering letter", "carta")

# Field types that carry a submit control rather than a value.
_SUBMIT_TYPES = frozenset({"submit", "button"})
_SUBMIT_LABEL_HINTS = ("submit", "apply", "send application", "enviar", "postular")


def _is_cv_input(field: FormField) -> bool:
    label = field.label.casefold()
    return field.field_type == "file" and any(h in label for h in _CV_LABEL_HINTS)


def _is_letter_input(field: FormField) -> bool:
    label = field.label.casefold()
    return field.field_type == "file" and any(h in label for h in _LETTER_LABEL_HINTS)


def _find_submit(observation: PageObservation) -> FormField | None:
    for field in observation.fields:
        if field.field_type in _SUBMIT_TYPES and any(
            hint in field.label.casefold() for hint in _SUBMIT_LABEL_HINTS
        ):
            return field
    return None


class FormAgentService:
    """Decides the single next action to take on an application form.

    Resolution is cheap-first and deliberately layered:

    1. A CAPTCHA or identity challenge escalates immediately, before any
       reasoning and regardless of confidence. There is no automated answer to
       "prove you are a human", and pretending otherwise is how accounts get
       banned.
    2. Document uploads are handled structurally, not by the model.
    3. Fields whose label maps onto a known profile key are filled verbatim
       from the profile, for free, and never reach an LLM.
    4. Only the *residual required* fields are sent to the model, in one batch.
    5. Every generated answer is passed through the grounding validator before
       the confidence gate sees it.

    The service is pure: it performs no I/O beyond the injected answerer port
    and holds no per-attempt state, so the caller drives the loop.
    """

    def __init__(
        self,
        answerer: FormAnswerPort,
        *,
        confidence_threshold: float,
        dry_run: bool,
    ) -> None:
        self._answerer = answerer
        self._threshold = confidence_threshold
        self._dry_run = dry_run

    async def next_action(
        self,
        *,
        observation: PageObservation,
        context: AgentContext,
    ) -> AgentAction:
        if observation.captcha_detected:
            return EscalateAction(
                reason="A CAPTCHA or identity challenge is blocking this form",
                fields=[],
            )

        upload = self._next_upload(observation, context)
        if upload is not None:
            return upload

        unfilled = [
            f for f in observation.fields if not f.is_filled and f.field_type not in _SUBMIT_TYPES
        ]

        deterministic = self._deterministic_fills(unfilled, context)
        if deterministic:
            return FillFieldsAction(fills=deterministic)

        residual = [f for f in unfilled if f.required and f.field_type != "file"]
        if residual:
            return await self._answer_residual(residual, context)

        return self._finish(observation, context)

    # --- steps -------------------------------------------------------------

    def _next_upload(
        self, observation: PageObservation, context: AgentContext
    ) -> UploadFileAction | None:
        for field in observation.fields:
            if field.is_filled:
                continue
            if context.needs_cv_upload and _is_cv_input(field):
                return UploadFileAction(selector=field.selector, artifact="cv")
            if context.needs_letter_upload and _is_letter_input(field):
                return UploadFileAction(selector=field.selector, artifact="cover_letter")
        return None

    def _deterministic_fills(
        self, unfilled: list[FormField], context: AgentContext
    ) -> list[FieldAnswer]:
        """Fill everything the label map recognises straight from the profile.

        These are copies of the candidate's own data, so they carry full
        confidence and are exempt from grounding: there is nothing generated
        here to hallucinate.
        """
        fills: list[FieldAnswer] = []
        for field in unfilled:
            if field.field_type == "file":
                continue
            key = match_canonical_key(field.label)
            if key is None or key not in context.prefill:
                continue
            fills.append(
                FieldAnswer(
                    selector=field.selector,
                    canonical_key=key,
                    value=str(context.prefill[key]),
                    confidence=1.0,
                    source=AnswerSource.DETERMINISTIC_MAP,
                    rationale="matched the canonical profile field map",
                )
            )
        return fills

    async def _answer_residual(
        self, residual: list[FormField], context: AgentContext
    ) -> AgentAction:
        answers = await self._answerer.answer(
            fields=residual,
            job_text=context.job_text,
            prefill=context.prefill,
            claim_texts=context.claim_texts,
            screening_answers=context.screening_answers,
        )
        answers = enforce_grounding(
            answers,
            prefill=context.prefill,
            claim_texts=context.claim_texts,
            job_text=context.job_text,
        )

        by_selector = {a.selector: a for a in answers}
        weak = [
            f.selector
            for f in residual
            if f.selector not in by_selector or by_selector[f.selector].confidence < self._threshold
        ]
        if weak:
            return EscalateAction(
                reason=self._escalation_reason(residual, by_selector, weak),
                fields=weak,
            )
        return FillFieldsAction(fills=[by_selector[f.selector] for f in residual])

    def _finish(self, observation: PageObservation, context: AgentContext) -> AgentAction:
        submit = _find_submit(observation)
        if submit is None:
            return EscalateAction(
                reason="Every field is filled but no submit control was found on the page",
                fields=[],
            )
        return SubmitAction(selector=submit.selector, dry_run=self._dry_run)

    @staticmethod
    def _escalation_reason(
        residual: list[FormField],
        by_selector: dict[str, FieldAnswer],
        weak: list[str],
    ) -> str:
        labels = {f.selector: f.label for f in residual}
        parts = []
        for selector in weak:
            answer = by_selector.get(selector)
            detail = answer.rationale if answer is not None and answer.rationale else "no answer"
            parts.append(f"{labels.get(selector, selector)} ({detail})")
        return "Needs a human answer: " + "; ".join(parts)
