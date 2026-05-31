from __future__ import annotations

from hiresense.preference.domain import PreferenceService


class PreferenceProvider:
    def __init__(self, preference_service: PreferenceService) -> None:
        self._preference_service = preference_service

    def get_preference_service(self) -> PreferenceService:
        return self._preference_service
