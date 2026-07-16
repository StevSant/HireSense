from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pymupdf

from hiresense.profile.domain.latex_parser import ParsedCV, ParsedSection

if TYPE_CHECKING:
    from hiresense.ports.llm import LLMPort

logger = logging.getLogger(__name__)

_EXTRACTION_SYSTEM_PROMPT = """\
You are a CV/resume parser. Extract structured information from the provided CV text.
Return ONLY valid JSON with this exact schema — no markdown, no explanation:
{
  "name": "Full Name",
  "email": "email@example.com or null",
  "phone": "phone number or null",
  "location": "location or null",
  "sections": [
    {"name": "Section Title", "content": "Section content as plain text"}
  ],
  "skills": ["skill1", "skill2"]
}
Rules:
- Extract ALL sections you can identify (Education, Experience, Skills, Projects, etc.)
- For skills, extract individual technical skills, tools, languages, and frameworks
- Keep section content as clean plain text, not HTML or LaTeX
- If a field is not found, use null (for strings) or [] (for arrays)
"""


class PDFParser:
    def __init__(self, llm: LLMPort | None = None, char_limit: int = 20000) -> None:
        self._llm = llm
        # Caps extracted CV text passed to the LLM extraction prompt — some
        # PDFs (multi-page portfolios, exported LinkedIn profiles) yield far
        # more raw text than a CV actually needs for structured extraction.
        self._char_limit = char_limit

    def extract_text(self, file_bytes: bytes) -> str:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)

    async def parse(self, file_bytes: bytes) -> ParsedCV:
        raw_text = self.extract_text(file_bytes)

        if self._llm is None:
            logger.warning(
                "No LLM configured — returning raw PDF text without structured extraction"
            )
            return ParsedCV(name="", raw_tex=raw_text)

        prompt = f"Extract structured information from this CV:\n\n{raw_text[: self._char_limit]}"
        response = await self._llm.complete(prompt, system=_EXTRACTION_SYSTEM_PROMPT)

        return self._parse_llm_response(response, raw_text)

    def _parse_llm_response(self, response: str, raw_text: str) -> ParsedCV:
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]

            data = json.loads(cleaned)
        except (json.JSONDecodeError, IndexError):
            logger.error("Failed to parse LLM response as JSON")
            return ParsedCV(name="", raw_tex=raw_text)

        sections = [
            ParsedSection(name=s.get("name", ""), content=s.get("content", ""))
            for s in data.get("sections", [])
            if s.get("name")
        ]

        return ParsedCV(
            name=data.get("name", ""),
            email=data.get("email"),
            phone=data.get("phone"),
            location=data.get("location"),
            sections=sections,
            raw_tex=raw_text,
        )
