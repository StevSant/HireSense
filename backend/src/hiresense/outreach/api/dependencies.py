from __future__ import annotations

from fastapi import Request

from hiresense.outreach.domain import OutreachService


def get_outreach_service(request: Request) -> OutreachService:
    return request.app.state.outreach.get_outreach_service()
