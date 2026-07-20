from __future__ import annotations

import json
import uuid

import pytest

from hiresense.interview.domain import InterviewPrepError, InterviewPrepService
from hiresense.ports import LLMTimeoutError


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, prompt, *, system="", model=""):
        return self._response


class FakeStoryRepo:
    def __init__(self, stories=None):
        self._stories = stories or []

    def list_all(self, competency=None):
        return self._stories


def _make_story(title="Led migration", competency="technical"):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=uuid.uuid4(),
        title=title,
        competency=competency,
        situation="Legacy system needed updating",
        task="Plan migration",
        action="Designed new architecture",
        result="Successful migration",
        reflection=None,
        tags=None,
    )


@pytest.mark.asyncio
async def test_prepare_returns_matched_stories():
    story = _make_story()
    llm_response = json.dumps(
        {
            "matched_stories": [
                {
                    "story_id": str(story.id),
                    "story_title": story.title,
                    "relevance": "Direct experience",
                }
            ],
            "competencies_to_probe": ["technical", "leadership"],
            "technical_topics": ["System design"],
            "negotiation_points": ["Remote flexibility"],
        }
    )
    service = InterviewPrepService(llm=FakeLLM(llm_response), story_repo=FakeStoryRepo([story]))
    result = await service.prepare(
        {"title": "SWE", "company": "Acme", "description": "Build stuff"}
    )
    assert len(result.matched_stories) == 1
    assert result.matched_stories[0].story_title == "Led migration"
    assert len(result.technical_topics) == 1


@pytest.mark.asyncio
async def test_prepare_no_stories():
    llm_response = json.dumps(
        {
            "matched_stories": [],
            "competencies_to_probe": ["problem_solving"],
            "technical_topics": ["APIs"],
            "negotiation_points": ["Equity"],
        }
    )
    service = InterviewPrepService(llm=FakeLLM(llm_response), story_repo=FakeStoryRepo())
    result = await service.prepare({"title": "SWE", "company": "X", "description": ""})
    assert result.matched_stories == []
    assert len(result.technical_topics) > 0


@pytest.mark.asyncio
async def test_prepare_no_llm():
    service = InterviewPrepService(llm=None, story_repo=FakeStoryRepo())
    result = await service.prepare({"title": "SWE", "company": "X", "description": ""})
    assert result.negotiation_points == ["LLM not configured"]


@pytest.mark.asyncio
async def test_prepare_raises_on_llm_failure():
    # A failing LLM must NOT return a benign placeholder that gets persisted as
    # real prep (#147) — it raises InterviewPrepError so the API returns 503.
    class FailingLLM:
        async def complete(self, prompt, *, system="", model=""):
            raise RuntimeError("API down")

    service = InterviewPrepService(llm=FailingLLM(), story_repo=FakeStoryRepo())
    with pytest.raises(InterviewPrepError):
        await service.prepare({"title": "SWE", "company": "X", "description": ""})


@pytest.mark.asyncio
async def test_prepare_raises_on_unparseable_response():
    service = InterviewPrepService(
        llm=FakeLLM("this is not json at all"), story_repo=FakeStoryRepo()
    )
    with pytest.raises(InterviewPrepError):
        await service.prepare({"title": "SWE", "company": "X", "description": ""})


@pytest.mark.asyncio
async def test_prepare_propagates_llm_timeout():
    # A timeout must surface as-is (mapped to 504 upstream), not be folded into a
    # generic InterviewPrepError (503).
    class TimingOutLLM:
        async def complete(self, prompt, *, system="", model=""):
            raise LLMTimeoutError(timeout=1.0, provider="anthropic")

    service = InterviewPrepService(llm=TimingOutLLM(), story_repo=FakeStoryRepo())
    with pytest.raises(LLMTimeoutError):
        await service.prepare({"title": "SWE", "company": "X", "description": ""})
