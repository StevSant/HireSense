from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hiresense.adapters.latex import LatexCompiler
from hiresense.applications.api.provider import ApplicationsProvider
from hiresense.applications.domain import ApplicationService, ArtifactService
from hiresense.applications.domain import SkillExtractor as ApplicationsSkillExtractor
from hiresense.applications.domain.apply_service import ApplyService
from hiresense.applications.domain.cover_letter_generator import CoverLetterGenerator
from hiresense.applications.infrastructure import ApplicationRepository
from hiresense.bootstrap.shared_infra import SharedInfra


def build_applications(
    infra: SharedInfra,
    tracked: Callable[[str], Any],
    *,
    tracking_service: Any,
    ingestion_orchestrator: Any,
    matching_orchestrator: Any,
    cv_optimizer: Any,
    interview_prep_service: Any,
    profile_service: Any,
) -> ApplicationsProvider:
    s = infra.settings
    application_repo = ApplicationRepository(session_factory=infra.sync_session_factory)
    applications_skill_extractor = ApplicationsSkillExtractor(
        llm=tracked("application_skill_extractor"),
    )
    application_service = ApplicationService(
        repository=application_repo,
        tracking_service=tracking_service,
        ingestion_orchestrator=ingestion_orchestrator,
        skill_extractor=applications_skill_extractor,
    )
    artifact_service = ArtifactService(
        repository=application_repo,
        matching_orchestrator=matching_orchestrator,
        cv_optimizer=cv_optimizer,
        interview_prep_service=interview_prep_service,
        profile_service=profile_service,
        tracking_service=tracking_service,
    )
    cover_letter_generator = CoverLetterGenerator(llm=tracked("cover_letter"))
    latex_compiler = LatexCompiler(
        compiler=s.latex_compiler,
        timeout_seconds=s.latex_timeout_seconds,
    )
    apply_service = ApplyService(
        repository=application_repo,
        cover_letter_generator=cover_letter_generator,
        latex_compiler=latex_compiler,
        profile_service=profile_service,
        tracking_service=tracking_service,
    )
    return ApplicationsProvider(
        application_service=application_service,
        artifact_service=artifact_service,
        apply_service=apply_service,
    )
