from __future__ import annotations

from fastapi import Request

from hiresense.inbox.api.provider import InboxProvider


def get_inbox_provider(request: Request) -> InboxProvider:
    return request.app.state.inbox
