from __future__ import annotations

import json
import re
import uuid as uuid_mod
from typing import Any

from pydantic import BaseModel

from hiresense.interview.domain.models import Competency, Story


class StoryMatch(BaseModel):
    story_id: uuid_mod.UUID
    story_title: str
    relevance: str


class InterviewPrep(BaseModel):
    job_title: str
    company: str
    matched_stories: list[StoryMatch]
    competencies_to_probe: list[str]
    technical_topics: list[str]
    negotiation_points: list[str]


class StoryService:
    def __init__(self, repository: Any) -> None:
        self._repo = repository

    def add_story(
        self,
        title: str,
        competency: Competency,
        situation: str,
        task: str,
        action: str,
        result: str,
        reflection: str | None = None,
        tags: str | None = None,
    ) -> Story:
        story = Story(
            title=title,
            competency=competency.value,
            situation=situation,
            task=task,
            action=action,
            result=result,
            reflection=reflection,
            tags=tags,
        )
        return self._repo.create(story)

    def get(self, id: uuid_mod.UUID) -> Story:
        story = self._repo.get_by_id(id)
        if story is None:
            raise ValueError(f"Story {id} not found")
        return story

    def list(self, competency: Competency | None = None) -> list[Story]:
        return self._repo.list_all(competency=competency)

    def update(self, id: uuid_mod.UUID, **fields) -> Story:
        story = self.get(id)
        for key, value in fields.items():
            setattr(story, key, value)
        return self._repo.save(story)

    def remove(self, id: uuid_mod.UUID) -> None:
        deleted = self._repo.delete(id)
        if not deleted:
            raise ValueError(f"Story {id} not found")


class InterviewPrepService:
    def __init__(self, llm, story_repo) -> None:
        self._llm = llm
        self._story_repo = story_repo

    async def prepare(self, job: dict) -> InterviewPrep:
        title = job.get("title", "")
        company = job.get("company", "")
        description = job.get("description", "")

        if self._llm is None:
            return InterviewPrep(
                job_title=title, company=company,
                matched_stories=[], competencies_to_probe=[],
                technical_topics=[], negotiation_points=["LLM not configured"],
            )

        stories = self._story_repo.list_all()
        valid_story_ids = {str(s.id) for s in stories}
        story_summaries = ""
        for i, s in enumerate(stories, 1):
            story_summaries += f"{i}. [{s.id}] \"{s.title}\" ({s.competency}) - {s.situation[:100]}\n"

        prompt = (
            "You are an interview preparation coach.\n\n"
            f"Job: {title} at {company}\nDescription: {description[:2000]}\n\n"
            f"Candidate's Story Bank:\n{story_summaries or 'No stories yet.'}\n\n"
            "Return JSON with:\n"
            "- matched_stories: [{story_id, story_title, relevance}] (only stories relevant to this job)\n"
            "- competencies_to_probe: [strings] (competencies likely tested in interview)\n"
            "- technical_topics: [strings] (topics to review)\n"
            "- negotiation_points: [strings] (salary/benefits talking points)\n\n"
            'Return valid JSON only: {"matched_stories": [...], "competencies_to_probe": [...], "technical_topics": [...], "negotiation_points": [...]}'
        )

        try:
            response = await self._llm.complete(prompt, system="You are an interview coach. Return only valid JSON.")
            data = None
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                md = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", response, re.DOTALL)
                if md:
                    data = json.loads(md.group(1))

            if data is None:
                raise ValueError("Could not parse LLM response")

            matched = [
                StoryMatch(story_id=m["story_id"], story_title=m["story_title"], relevance=m["relevance"])
                for m in data.get("matched_stories", [])
                if str(m.get("story_id", "")) in valid_story_ids
            ]
            return InterviewPrep(
                job_title=title, company=company,
                matched_stories=matched,
                competencies_to_probe=data.get("competencies_to_probe", []),
                technical_topics=data.get("technical_topics", []),
                negotiation_points=data.get("negotiation_points", []),
            )
        except Exception as exc:
            return InterviewPrep(
                job_title=title, company=company,
                matched_stories=[], competencies_to_probe=[],
                technical_topics=[], negotiation_points=["Interview preparation is temporarily unavailable"],
            )
