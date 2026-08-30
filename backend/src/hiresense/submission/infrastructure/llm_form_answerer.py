from __future__ import annotations

import json
import logging
import re

from hiresense.shared.ports import LLMPort
from hiresense.submission.domain import AnswerSource, FieldAnswer, FormField
from hiresense.submission.domain.form_answer_prompt import (
    SYSTEM_PROMPT,
    build_form_answer_prompt,
)

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _extract_json(raw: str) -> dict | None:
    """Pull the JSON object out of a model response, fences and all."""
    text = _FENCE.sub("", raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


class LLMFormAnswerer:
    """Answers residual form fields via the shared LLM port.

    Never raises on bad model output. A malformed response yields no answers,
    which the confidence gate reads as "escalate to the human" -- the correct
    failure direction for a system that submits under someone's name.
    """

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def answer(
        self,
        *,
        fields: list[FormField],
        job_text: str,
        prefill: dict[str, object],
        claim_texts: list[str],
        screening_answers: list[tuple[str, str]],
    ) -> list[FieldAnswer]:
        if not fields:
            return []
        prompt = build_form_answer_prompt(
            fields=fields,
            job_text=job_text,
            prefill=prefill,
            claim_texts=claim_texts,
            screening_answers=screening_answers,
        )
        try:
            raw = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:  # noqa: BLE001 - a provider failure escalates, never crashes
            logger.exception("submission: form answerer LLM call failed")
            return []

        parsed = _extract_json(raw)
        if parsed is None:
            logger.warning("submission: form answerer returned unparseable output")
            return []

        known = {f.selector for f in fields}
        answers: list[FieldAnswer] = []
        for item in parsed.get("answers") or []:
            if not isinstance(item, dict):
                continue
            selector = item.get("selector")
            if selector not in known:
                # The model answered a field that is not on this page. Dropping
                # it is safer than guessing which one it meant.
                continue
            value = item.get("value")
            if not isinstance(value, str):
                continue
            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            answers.append(
                FieldAnswer(
                    selector=selector,
                    canonical_key=item.get("canonical_key"),
                    value=value,
                    confidence=min(max(confidence, 0.0), 1.0),
                    source=AnswerSource.LLM,
                    rationale=item.get("rationale"),
                )
            )
        return answers
