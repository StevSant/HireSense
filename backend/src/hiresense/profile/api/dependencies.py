from __future__ import annotations

from fastapi import Request

from hiresense.profile.domain import ProfileService


def get_profile_service(request: Request) -> ProfileService:
    return request.app.state.profile.get_profile_service()
