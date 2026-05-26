from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from hiresense.profile.domain.latex_parser import LaTeXParser, ParsedCV
from hiresense.profile.domain.models import CandidateProfile, CVSection, Profile
from hiresense.profile.domain.profile_language_view import ProfileLanguageView
from hiresense.profile.domain.skill_extractor import SkillExtractor

SUMMARY_MAX_CHARS = 2000

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
        shared_links = self._inherit_shared_links()
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
            **shared_links,
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

        shared_links = self._inherit_shared_links()
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
            **shared_links,
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

    def get_for_language(self, language: str) -> ProfileLanguageView | None:
        """Sync uniform view of the latest profile for a given language.

        Returns None if no profile exists for that language.
        """
        profile = self._get_latest_for_language_sync(language)
        if profile is None:
            return None
        summary = "\n\n".join(s.content for s in profile.sections)[:SUMMARY_MAX_CHARS]
        return ProfileLanguageView(
            language=profile.language,
            summary=summary,
            skills=list(profile.skills or []),
            raw_tex=profile.raw_tex or "",
        )

    def _get_latest_for_language_sync(self, language: str) -> CandidateProfile | None:
        if self._repository is not None:
            orm = self._repository.get_latest(language=language)
            return self._to_response(orm) if orm else None
        profiles = [p for p in self._profiles.values() if p.language == language]
        return profiles[-1] if profiles else None

    EDITABLE_FIELDS = (
        "name",
        "email",
        "phone",
        "location",
        "linkedin_url",
        "github_url",
        "portfolio_url",
    )

    # Fields that belong to the person, not the language variant. Edits to
    # these are broadcast across all profile rows so the Spanish and English
    # CVs share the same LinkedIn/GitHub/portfolio link.
    _SHARED_FIELDS = ("linkedin_url", "github_url", "portfolio_url")

    async def update_manual_fields(
        self, profile_id: str, fields: dict[str, str | None]
    ) -> CandidateProfile | None:
        """Apply user-editable overrides to a stored profile.

        Only whitelisted fields are accepted. Empty strings are stored as
        NULL so the UI can fall back to CV-parsed values when needed.
        """
        sanitised: dict[str, str | None] = {}
        for key in self.EDITABLE_FIELDS:
            if key not in fields:
                continue
            value = fields[key]
            if isinstance(value, str):
                value = value.strip()
                value = value or None
            sanitised[key] = value

        if not sanitised:
            return await self.get_profile(profile_id)

        shared = {k: v for k, v in sanitised.items() if k in self._SHARED_FIELDS}
        per_language = {k: v for k, v in sanitised.items() if k not in self._SHARED_FIELDS}

        if self._repository is not None:
            if shared:
                self._repository.update_all(shared)
            if per_language:
                orm = self._repository.update(uuid.UUID(profile_id), per_language)
            else:
                orm = self._repository.get_by_id(uuid.UUID(profile_id))
            return self._to_response(orm) if orm else None

        # In-memory fallback (tests / legacy path)
        profile = self._profiles.get(profile_id)
        if profile is None:
            return None
        if shared:
            for pid, p in list(self._profiles.items()):
                self._profiles[pid] = p.model_copy(update=shared)
        if per_language:
            current = self._profiles[profile_id]
            self._profiles[profile_id] = current.model_copy(update=per_language)
        return self._profiles[profile_id]

    async def list_profiles(self) -> list[CandidateProfile]:
        """Return the latest profile per language (deduplicated)."""
        if self._repository is not None:
            orms = self._repository.list_all()
            all_profiles = [self._to_response(orm) for orm in orms]
        else:
            all_profiles = list(self._profiles.values())

        # Keep only the latest (first, since ordered by created_at DESC) per language
        seen_languages: set[str] = set()
        result: list[CandidateProfile] = []
        for profile in all_profiles:
            if profile.language not in seen_languages:
                seen_languages.add(profile.language)
                result.append(profile)
        return result

    _SKILL_SECTION_KEYWORDS = {"SKILL", "HABILIDAD", "COMPETENCIA", "TÉCNICA", "TECNICA"}

    def _inherit_shared_links(self) -> dict[str, str | None]:
        """Read shared link fields from any existing profile so newly uploaded
        language variants don't lose the user's LinkedIn/GitHub/portfolio."""
        source: CandidateProfile | None = None
        if self._repository is not None:
            orm = self._repository.get_latest()
            if orm is not None:
                source = self._to_response(orm)
        else:
            profiles = list(self._profiles.values())
            source = profiles[-1] if profiles else None
        if source is None:
            return {}
        return {field: getattr(source, field) for field in self._SHARED_FIELDS}

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
            linkedin_url=profile.linkedin_url,
            github_url=profile.github_url,
            portfolio_url=profile.portfolio_url,
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
            linkedin_url=orm.linkedin_url,
            github_url=orm.github_url,
            portfolio_url=orm.portfolio_url,
        )
