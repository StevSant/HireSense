from __future__ import annotations

from fastapi import Request

from hiresense.preference.domain import PreferenceService


def get_preference_service(request: Request) -> PreferenceService:
    return request.app.state.preference.get_preference_service()
