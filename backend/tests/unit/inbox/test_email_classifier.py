from datetime import datetime, timezone

import pytest

from hiresense.inbox.domain import EmailClassifier, EmailSignalKind, InboundEmail


class _LLM:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise = raise_exc

    async def complete(self, prompt, system=""):
        if self._raise is not None:
            raise self._raise
        return self._response


def _email():
    return InboundEmail(
        message_id="m1",
        from_address="r@acme.com",
        subject="Your application",
        body="We regret to inform you...",
        received_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_parses_structured_json():
    llm = _LLM(
        response='{"job_related": true, "kind": "rejection", "company": "Acme", "role": "Dev", "confidence": 0.9}'
    )
    result = await EmailClassifier(llm).classify(_email())
    assert result.job_related is True
    assert result.kind is EmailSignalKind.REJECTION
    assert result.company == "Acme"
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_llm_error_returns_not_job_related():
    result = await EmailClassifier(_LLM(raise_exc=RuntimeError("boom"))).classify(_email())
    assert result.job_related is False


@pytest.mark.asyncio
async def test_unparseable_response_returns_not_job_related():
    result = await EmailClassifier(_LLM(response="not json at all")).classify(_email())
    assert result.job_related is False


@pytest.mark.asyncio
async def test_no_llm_returns_not_job_related():
    result = await EmailClassifier(None).classify(_email())
    assert result.job_related is False
