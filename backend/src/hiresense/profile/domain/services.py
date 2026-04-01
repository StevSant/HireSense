from __future__ import annotations

import uuid

from hiresense.profile.domain.latex_parser import LaTeXParser
from hiresense.profile.domain.models import CandidateProfile, CVSection
from hiresense.profile.domain.skill_extractor import SkillExtractor


class ProfileService:
    def __init__(self, parser: LaTeXParser, skill_extractor: SkillExtractor) -> None:
        self._parser = parser
        self._skill_extractor = skill_extractor
        self._profiles: dict[str, CandidateProfile] = {}

    async def parse_and_create(self, tex_content: str, language: str = "en") -> CandidateProfile:
        parsed = self._parser.parse(tex_content)

        # Extract skills from TECHNICAL SKILLS section if found
        skills: list[str] = []
        for section in parsed.sections:
            if "SKILL" in section.name.upper():
                skills = self._skill_extractor.extract_from_tabular(section.content)
                break

        sections = [CVSection(name=s.name, content=s.content) for s in parsed.sections]

        profile = CandidateProfile(
            id=str(uuid.uuid4()),
            name=parsed.name,
            email=parsed.email,
            phone=parsed.phone,
            location=parsed.location,
            sections=sections,
            raw_tex=tex_content,
            language=language,
            skills=skills,
        )
        self._profiles[profile.id] = profile
        return profile

    async def get_profile(self, profile_id: str) -> CandidateProfile | None:
        return self._profiles.get(profile_id)
