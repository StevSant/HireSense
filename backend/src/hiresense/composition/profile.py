from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.shared.adapters.latex import LatexCompiler
from hiresense.shared.adapters.llm import NullLLM
from hiresense.composition.shared_infra import SharedInfra
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
    pdf_parser = PDFParser(llm=tracked("cv_parser"), char_limit=infra.settings.cv_parse_char_limit)
    skill_extractor = SkillExtractor()
    # `tracked` yields None when no LLM_API_KEY is configured (APP_MODE=local).
    # The translator has no meaningful degraded output — a CV it can't translate
    # is not a CV — so it gets a NullLLM that raises LLMNotConfiguredError,
    # which the route surfaces as a 503 exactly as the old None-guard did.
    translator = CVTranslator(llm=tracked("cv_translator") or NullLLM(feature="cv_translator"))
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
