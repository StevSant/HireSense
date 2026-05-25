from hiresense.profile.cover_letter_templates.create_request import (
    CreateCoverLetterTemplateRequest,
)
from hiresense.profile.cover_letter_templates.dependencies import (
    get_cover_letter_template_service,
)
from hiresense.profile.cover_letter_templates.orm import CoverLetterTemplate
from hiresense.profile.cover_letter_templates.provider import CoverLetterTemplateProvider
from hiresense.profile.cover_letter_templates.repository import CoverLetterTemplateRepository
from hiresense.profile.cover_letter_templates.routes import router as cover_letter_templates_router
from hiresense.profile.cover_letter_templates.service import CoverLetterTemplateService
from hiresense.profile.cover_letter_templates.update_request import (
    UpdateCoverLetterTemplateRequest,
)
from hiresense.profile.cover_letter_templates.view import CoverLetterTemplateView

__all__ = [
    "CoverLetterTemplate",
    "CoverLetterTemplateProvider",
    "CoverLetterTemplateRepository",
    "CoverLetterTemplateService",
    "CoverLetterTemplateView",
    "CreateCoverLetterTemplateRequest",
    "UpdateCoverLetterTemplateRequest",
    "cover_letter_templates_router",
    "get_cover_letter_template_service",
]
