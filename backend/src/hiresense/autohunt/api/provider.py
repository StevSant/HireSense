from __future__ import annotations

from hiresense.autohunt.domain import AutoHuntService


class AutoHuntProvider:
    def __init__(self, autohunt_service: AutoHuntService) -> None:
        self._autohunt_service = autohunt_service

    def get_autohunt_service(self) -> AutoHuntService:
        return self._autohunt_service
