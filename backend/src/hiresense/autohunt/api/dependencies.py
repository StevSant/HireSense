from __future__ import annotations

from fastapi import Request

from hiresense.autohunt.domain import AutoHuntService


def get_autohunt_service(request: Request) -> AutoHuntService:
    return request.app.state.autohunt.get_autohunt_service()
