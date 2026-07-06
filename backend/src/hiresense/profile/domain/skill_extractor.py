from __future__ import annotations

import json
import re
from typing import Any


class SkillExtractor:
    """Extracts skills from parsed CV sections using regex or LLM."""

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm

    def extract_from_tabular(self, content: str) -> list[str]:
        """Extract skills from LaTeX tabular content (regex-based, no LLM needed)."""
        pattern = r"\\textbf\{[^}]+:\}\s*&\s*(.+?)(?:\\\\|$)"
        matches = re.findall(pattern, content)

        seen: set[str] = set()
        skills: list[str] = []

        for match in matches:
            for skill in match.split(","):
                cleaned = skill.strip().rstrip("\\").strip()
                if cleaned and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    skills.append(cleaned)

        return skills

    async def extract_with_llm(self, text: str) -> list[str]:
        """Extract skills using LLM for unstructured text."""
        if self._llm is None:
            return []

        prompt = (
            "Extract all technical skills, tools, frameworks, and programming languages "
            "from the following text. Return ONLY a JSON array of lowercase strings, "
            "nothing else.\n\n"
            f"Text: {text}"
        )
        response = await self._llm.complete(prompt, system="You are a skill extraction assistant.")

        cleaned = response.strip()
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        try:
            skills = json.loads(cleaned)
            if isinstance(skills, list):
                return [s.strip().lower() for s in skills if isinstance(s, str)]
        except (json.JSONDecodeError, TypeError):
            pass

        return []
