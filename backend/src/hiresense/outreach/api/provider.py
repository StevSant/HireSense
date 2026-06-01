from __future__ import annotations

from hiresense.outreach.domain import OutreachService


class OutreachProvider:
    def __init__(self, outreach_service: OutreachService) -> None:
        self._outreach_service = outreach_service

    def get_outreach_service(self) -> OutreachService:
        return self._outreach_service
