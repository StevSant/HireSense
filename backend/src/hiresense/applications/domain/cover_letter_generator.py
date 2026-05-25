from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You write concise, professional cover letters tailored to a specific job. "
    "Match the candidate's strengths to the role's requirements. No fluff."
)

USER_PROMPT_TEMPLATE = (
    "Write a cover letter for the following job application.\n\n"
    "Job Title: {title}\n"
    "Company: {company}\n"
    "Job Description:\n{description}\n\n"
    "Candidate Summary:\n{candidate_summary}\n\n"
    "Candidate Skills: {candidate_skills}\n"
    "Required Skills: {required_skills}\n"
    "Strengths to emphasize (from match analysis): {pros}\n"
    "Gaps the candidate has (acknowledge briefly, do not dwell): {missing_skills}\n\n"
    "Constraints:\n"
    "- Tone: {tone}\n"
    "- 3-4 paragraphs, total 200-350 words\n"
    "- Open with a specific reason for applying to {company}\n"
    "- Middle paragraphs: tie 2-3 concrete strengths to job needs\n"
    "- Close with a clear call to action\n"
    "- Plain text, no markdown, no headers, no salutation placeholders like [Name]\n\n"
    "Return only the cover letter body."
)


TEMPLATE_PROMPT_SUFFIX = (
    "\n\nStylistic reference (a previous cover letter the candidate liked — match its "
    "voice, structure, and signature, but do NOT copy text verbatim and DO tailor the "
    "content to the specific job above):\n---\n{template_body}\n---"
)


class CoverLetterGenerator:
    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def generate(
        self,
        *,
        title: str,
        company: str,
        description: str,
        candidate_summary: str,
        candidate_skills: list[str],
        required_skills: list[str],
        pros: list[str],
        missing_skills: list[str],
        tone: str = "professional",
        template_body: str | None = None,
    ) -> str:
        if self._llm is None:
            raise RuntimeError("LLM not configured — cover letter generation unavailable")

        prompt = USER_PROMPT_TEMPLATE.format(
            title=title,
            company=company,
            description=description,
            candidate_summary=candidate_summary,
            candidate_skills=", ".join(candidate_skills) or "(none provided)",
            required_skills=", ".join(required_skills) or "(none provided)",
            pros=", ".join(pros) or "(none)",
            missing_skills=", ".join(missing_skills) or "(none)",
            tone=tone,
        )
        if template_body and template_body.strip():
            prompt += TEMPLATE_PROMPT_SUFFIX.format(template_body=template_body.strip())
        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:
            logger.exception("Cover letter LLM call failed")
            raise
        return response.strip()
