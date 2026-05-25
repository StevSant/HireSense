from __future__ import annotations

from hiresense.profile.cover_letter_templates.service import CoverLetterTemplateService


class CoverLetterTemplateProvider:
    def __init__(self, service: CoverLetterTemplateService) -> None:
        self._service = service

    def get_service(self) -> CoverLetterTemplateService:
        return self._service
