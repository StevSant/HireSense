from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from hiresense.profile.domain.latex_parser import LaTeXParser, ParsedCV
from hiresense.profile.domain.models import CandidateProfile, CVSection, Profile
from hiresense.profile.domain.skill_extractor import SkillExtractor

if TYPE_CHECKING:
    from hiresense.profile.domain.pdf_parser import PDFParser
    from hiresense.profile.ports.repository import ProfileRepositoryPort

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(
        self,
        parser: LaTeXParser,
        skill_extractor: SkillExtractor,
        repository: ProfileRepositoryPort | None = None,
        pdf_parser: PDFParser | None = None,
        cv_directory: str = "./cvs",
    ) -> None:
        self._parser = parser
        self._skill_extractor = skill_extractor
        self._repository = repository
        self._pdf_parser = pdf_parser
        self._cv_directory = Path(cv_directory)
        self._profiles: dict[str, CandidateProfile] = {}

    async def parse_and_create(self, tex_content: str, language: str = "en") -> CandidateProfile:
        parsed = self._parser.parse(tex_content)

        # Extract skills from raw LaTeX content (before stripping)
        skills = self._extract_skills_from_parsed(parsed)

        # Strip LaTeX for display
        cleaned_sections = self._parser.strip_section_content(parsed.sections)
        sections = [CVSection(name=s.name, content=s.content) for s in cleaned_sections]

        profile_id = str(uuid.uuid4())
        profile = CandidateProfile(
            id=profile_id,
            name=parsed.name,
            email=parsed.email,
            phone=parsed.phone,
            location=parsed.location,
            sections=sections,
            raw_tex=tex_content,
            language=language,
            skills=skills,
        )

        if self._repository is not None:
            orm_profile = self._to_orm(profile)
            self._repository.create(orm_profile)
        else:
            self._profiles[profile.id] = profile

        return profile

    async def parse_file_and_create(
        self, file_bytes: bytes, filename: str, language: str = "en"
    ) -> CandidateProfile:
        ext = Path(filename).suffix.lower()

        if ext == ".pdf":
            if self._pdf_parser is None:
                msg = "PDF parsing not available — no PDFParser configured"
                raise ValueError(msg)
            parsed = await self._pdf_parser.parse(file_bytes)
            skills = self._extract_skills_from_parsed(parsed)
        elif ext == ".tex":
            content = file_bytes.decode("utf-8", errors="replace")
            parsed = self._parser.parse(content)
            skills = self._extract_skills_from_parsed(parsed)
        else:
            msg = f"Unsupported file type: {ext}"
            raise ValueError(msg)

        profile_id = str(uuid.uuid4())
        self._save_original_file(profile_id, filename, file_bytes)

        # Strip LaTeX for display
        cleaned_sections = self._parser.strip_section_content(parsed.sections)
        sections = [CVSection(name=s.name, content=s.content) for s in cleaned_sections]

        profile = CandidateProfile(
            id=profile_id,
            name=parsed.name,
            email=parsed.email,
            phone=parsed.phone,
            location=parsed.location,
            sections=sections,
            raw_tex=parsed.raw_tex,
            language=language,
            skills=skills,
        )

        if self._repository is not None:
            orm_profile = self._to_orm(profile, original_filename=filename)
            self._repository.create(orm_profile)
        else:
            self._profiles[profile.id] = profile

        return profile

    async def get_profile(self, profile_id: str) -> CandidateProfile | None:
        if self._repository is not None:
            orm = self._repository.get_by_id(uuid.UUID(profile_id))
            return self._to_response(orm) if orm else None
        return self._profiles.get(profile_id)

    async def get_current_profile(self, language: str | None = None) -> CandidateProfile | None:
        if self._repository is not None:
            orm = self._repository.get_latest(language=language)
            return self._to_response(orm) if orm else None
        # In-memory fallback
        profiles = list(self._profiles.values())
        if language:
            profiles = [p for p in profiles if p.language == language]
        return profiles[-1] if profiles else None

    async def list_profiles(self) -> list[CandidateProfile]:
        if self._repository is not None:
            orms = self._repository.list_all()
            return [self._to_response(orm) for orm in orms]
        return list(self._profiles.values())

    _SKILL_SECTION_KEYWORDS = {"SKILL", "HABILIDAD", "COMPETENCIA", "TÉCNICA", "TECNICA"}

    def _extract_skills_from_parsed(self, parsed: ParsedCV) -> list[str]:
        for section in parsed.sections:
            name_upper = section.name.upper()
            if any(kw in name_upper for kw in self._SKILL_SECTION_KEYWORDS):
                return self._skill_extractor.extract_from_tabular(section.content)
        return []

    def _save_original_file(self, profile_id: str, filename: str, file_bytes: bytes) -> None:
        originals_dir = self._cv_directory / "originals"
        originals_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        dest = originals_dir / f"{profile_id}_{safe_name}"
        dest.write_bytes(file_bytes)
        logger.info("Saved original CV to %s", dest)

    def _to_orm(
        self, profile: CandidateProfile, original_filename: str | None = None
    ) -> Profile:
        return Profile(
            id=uuid.UUID(profile.id),
            name=profile.name,
            email=profile.email,
            phone=profile.phone,
            location=profile.location,
            sections=[{"name": s.name, "content": s.content} for s in profile.sections],
            raw_tex=profile.raw_tex,
            language=profile.language,
            skills=profile.skills,
            original_filename=original_filename,
        )

    def _to_response(self, orm: Profile) -> CandidateProfile:
        sections = [
            CVSection(name=s.get("name", ""), content=s.get("content", ""))
            for s in (orm.sections or [])
        ]
        return CandidateProfile(
            id=str(orm.id),
            name=orm.name,
            email=orm.email,
            phone=orm.phone,
            location=orm.location,
            sections=sections,
            raw_tex=orm.raw_tex or "",
            language=orm.language,
            skills=orm.skills or [],
        )
