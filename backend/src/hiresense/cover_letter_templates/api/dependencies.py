from __future__ import annotations

from fastapi import Request

from hiresense.cover_letter_templates.domain.services import CoverLetterTemplateService


def get_template_service(request: Request) -> CoverLetterTemplateService:
    return request.app.state.cover_letter_templates.get_service()
