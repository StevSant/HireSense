from __future__ import annotations

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.cover_letter_templates.api.provider import CoverLetterTemplateProvider
from hiresense.cover_letter_templates.domain import CoverLetterTemplateService
from hiresense.cover_letter_templates.infrastructure import CoverLetterTemplateRepository


def build_cover_letter_templates(infra: SharedInfra) -> CoverLetterTemplateProvider:
    template_repo = CoverLetterTemplateRepository(session_factory=infra.sync_session_factory)
    template_service = CoverLetterTemplateService(repository=template_repo)
    return CoverLetterTemplateProvider(service=template_service)
