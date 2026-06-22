from __future__ import annotations

import json
import logging
from typing import Any

from hiresense.inbox.domain.classification import EmailClassification
from hiresense.inbox.domain.email_signal_kind import EmailSignalKind
from hiresense.inbox.domain.inbound_email import InboundEmail

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You classify recruiting emails. Decide if the email concerns a job "
    "application the recipient made, and which status signal it carries. "
    'Respond with ONLY a JSON object: {"job_related": bool, "kind": one of '
    '"rejection"|"interview"|"offer"|"other", "company": string or null, '
    '"role": string or null, "confidence": number 0..1}. No prose, no markdown.'
)


class EmailClassifier:
    """Pure LLM unit: classify an inbound email into a status signal. Never
    raises — an LLM or parse failure yields job_related=False."""

    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def classify(self, email: InboundEmail) -> EmailClassification:
        if self._llm is None:
            return EmailClassification(job_related=False)
        prompt = (
            f"From: {email.from_address}\n"
            f"Subject: {email.subject}\n\n"
            f"{email.body[:4000]}"
        )
        try:
            raw = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:  # noqa: BLE001 - classification is best-effort
            logger.exception("inbox: classifier LLM call failed")
            return EmailClassification(job_related=False)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> EmailClassification:
        try:
            data = json.loads(raw.strip())
            kind = EmailSignalKind(data.get("kind", "other"))
            return EmailClassification(
                job_related=bool(data.get("job_related", False)),
                kind=kind,
                company=data.get("company"),
                role=data.get("role"),
                confidence=float(data.get("confidence", 0.0)),
            )
        except Exception:  # noqa: BLE001 - tolerate any malformed LLM output
            logger.warning("inbox: could not parse classifier output")
            return EmailClassification(job_related=False)
