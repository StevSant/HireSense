from __future__ import annotations

from fastapi import Request

from hiresense.submission.api.provider import SubmissionProvider


def get_submission_provider(request: Request) -> SubmissionProvider:
    return request.app.state.submission
