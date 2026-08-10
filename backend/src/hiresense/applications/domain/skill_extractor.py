from __future__ import annotations

import logging
from typing import Any

from hiresense.shared.kernel import extract_json
from hiresense.shared.kernel.prompt_boundary import PromptBoundary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You extract required technical skills from job descriptions. "
    f"{PromptBoundary.untrusted_content_instruction()} Return only a JSON array."
)
USER_PROMPT_TEMPLATE = (
    "Extract the required technical skills from the following job description. "
    "Return a JSON array of short lowercase strings (no commentary, no markdown, no explanation). "
    "Skills are libraries, languages, frameworks, tools, databases, cloud providers, "
    "and other technical competencies. Exclude soft skills.\n\n"
    "Job description:\n{description}"
)


class SkillExtractor:
    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def extract(self, description: str) -> list[str]:
        if self._llm is None or not description.strip():
            return []

        prompt = USER_PROMPT_TEMPLATE.format(
            description=PromptBoundary.untrusted_job_content(description, max_chars=12000)
        )
        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:
            logger.exception("Skill extraction LLM call failed")
            return []

        parsed = extract_json(response)
        if not isinstance(parsed, list):
            logger.warning("Skill extractor got non-JSON-array response: %r", response[:200])
            return []

        return self._normalize(parsed)

    @staticmethod
    def _normalize(skills: list[Any]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for s in skills:
            if not isinstance(s, str):
                continue
            normalized = s.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result
