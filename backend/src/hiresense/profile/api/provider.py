from __future__ import annotations

from hiresense.profile.domain import ProfileService


class ProfileProvider:
    def __init__(self, profile_service: ProfileService) -> None:
        self._profile_service = profile_service

    def get_profile_service(self) -> ProfileService:
        return self._profile_service
