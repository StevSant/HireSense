from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.adapters.latex import LatexCompiler
from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.profile.api.provider import ProfileProvider
from hiresense.profile.domain import (
    CVTranslator,
    LaTeXParser,
    PDFParser,
    ProfileService,
    SkillExtractor,
)
from hiresense.profile.infrastructure import ProfileRepository


@dataclass(frozen=True)
class ProfileBuild:
    provider: ProfileProvider
    service: ProfileService


def build_profile(infra: SharedInfra, tracked: Callable[[str], Any]) -> ProfileBuild:
    profile_repo = ProfileRepository(session_factory=infra.sync_session_factory)
    latex_parser = LaTeXParser()
    pdf_parser = PDFParser(llm=tracked("cv_parser"))
    skill_extractor = SkillExtractor()
    translator = CVTranslator(llm=tracked("cv_translator"))
    latex_compiler = LatexCompiler(
        compiler=infra.settings.latex_compiler,
        timeout_seconds=infra.settings.latex_timeout_seconds,
    )
    profile_service = ProfileService(
        parser=latex_parser,
        skill_extractor=skill_extractor,
        repository=profile_repo,
        pdf_parser=pdf_parser,
        cv_directory=infra.settings.cv_directory,
        translator=translator,
        latex_compiler=latex_compiler,
    )
    provider = ProfileProvider(profile_service=profile_service)
    return ProfileBuild(provider=provider, service=profile_service)
