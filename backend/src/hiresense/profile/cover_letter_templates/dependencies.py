from __future__ import annotations

from fastapi import Request

from hiresense.profile.cover_letter_templates.service import CoverLetterTemplateService


def get_cover_letter_template_service(request: Request) -> CoverLetterTemplateService:
    return request.app.state.cover_letter_templates.get_service()
