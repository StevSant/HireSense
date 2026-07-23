from __future__ import annotations

import logging
from typing import Any

from hiresense.kernel.prompt_boundary import PromptBoundary

logger = logging.getLogger(__name__)


class OutreachUnavailableError(RuntimeError):
    """Raised when outreach generation is requested but no LLM is configured."""


SYSTEM_PROMPT = (
    "You draft short, on-brand outreach messages to recruiters and hiring "
    "managers. Concise, specific, and genuine. No fluff, no placeholders, no "
    "markdown. "
    f"{PromptBoundary.untrusted_content_instruction()} "
    "Return only the message body, ready to paste."
)


class OutreachMessageGenerator:
    """Pure LLM unit. Inputs are resolved by OutreachService."""

    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def generate(
        self,
        *,
        company: str,
        title: str,
        job_description: str,
        candidate_name: str,
        candidate_summary: str,
        candidate_skills: list[str],
        company_research: str | None,
        contact_name: str | None,
        style_guide: str,
        channel: str | None,
        max_chars: int,
        portfolio_section: str | None = None,
    ) -> str:
        if self._llm is None:
            raise OutreachUnavailableError("no LLM configured")

        parts = [
            f"Draft an outreach message following this style guide:\n---\n{style_guide}\n---\n",
            f"Role: {title} at {company}",
            f"Job context: {PromptBoundary.untrusted_job_content(job_description, max_chars=1200)}",
            f"Candidate name (sign with this): {candidate_name or '(unknown)'}",
            f"Candidate summary: {candidate_summary or '(none)'}",
            f"Candidate skills: {', '.join(candidate_skills) or '(none)'}",
        ]
        if company_research:
            parts.append(f"Company research (use lightly): {company_research}")
        if contact_name:
            parts.append(f"Address it to: {contact_name}")
        if channel:
            parts.append(f"Channel: {channel}")
        if portfolio_section:
            parts.append(portfolio_section)
            parts.append(
                "Mention at most ONE of these projects, only if it strengthens the hook; "
                "if a portfolio link is given above, include it verbatim."
            )
        parts.append(
            f"Keep it under ~{max_chars} characters. Greet (use the contact name "
            "if given), state the role and one specific genuine hook tying the "
            "candidate's strengths to the company, a light call to connect, and "
            "sign with the candidate's name. Return only the message body."
        )
        prompt = "\n".join(parts)
        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:
            logger.exception("outreach: LLM call failed")
            raise
        return response.strip()
