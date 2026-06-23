from __future__ import annotations

from fastapi import Request

from hiresense.autopilot.api.provider import AutopilotProvider


def get_autopilot_provider(request: Request) -> AutopilotProvider:
    return request.app.state.autopilot
