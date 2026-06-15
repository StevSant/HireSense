from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_MARKDOWN_FENCE_RE = re.compile(r"```(?:[a-zA-Z]+)?\s*\n?(.*?)\n?```", re.DOTALL)

_LANG_NAMES = {"en": "English", "es": "Spanish"}


class CVTranslator:
    """Translates a CV's LaTeX source into another language via the LLM.

    Only human-readable text is translated; every LaTeX command, environment,
    option, and structural token is preserved so the result still compiles.
    """

    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def translate(self, raw_tex: str, source_lang: str, target_lang: str) -> str:
        if self._llm is None:
            raise RuntimeError("LLM not configured — cannot translate CV")
        prompt = self._build_prompt(raw_tex, source_lang, target_lang)
        response = await self._llm.complete(
            prompt,
            system="You are an expert technical translator for LaTeX résumés.",
        )
        return self._strip_fence(response)

    def _build_prompt(self, raw_tex: str, source_lang: str, target_lang: str) -> str:
        source_name = _LANG_NAMES.get(source_lang, source_lang)
        target_name = _LANG_NAMES.get(target_lang, target_lang)
        return (
            f"Translate the following LaTeX résumé from {source_name} to {target_name}.\n\n"
            "STRICT RULES:\n"
            "- Translate ONLY human-readable text: section bodies, headings, prose, bullet points.\n"
            "- Do NOT alter, remove, or reorder any LaTeX command, environment, option, or "
            "argument structure (e.g. \\section, \\begin{...}, \\textbf{...}, column specs, "
            "braces, backslashes).\n"
            "- Do NOT translate URLs, email addresses, phone numbers, technology names "
            "(e.g. Python, FastAPI, PostgreSQL), company names, or person names.\n"
            "- Keep all whitespace structure and the document preamble intact.\n"
            "- Return ONLY the complete translated .tex document, with no commentary "
            "and no markdown fences.\n\n"
            f"LaTeX source:\n{raw_tex}"
        )

    @staticmethod
    def _strip_fence(text: str) -> str:
        match = _MARKDOWN_FENCE_RE.search(text)
        return (match.group(1) if match else text).strip()
