from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel


class SkillGapItem(BaseModel):
    skill: str
    count: int
    pct: float


class SkillGap(BaseModel):
    has_profile: bool
    missing: list[SkillGapItem]


class SkillGapService:
    def __init__(self, corpus: Any, normalizer: Any) -> None:
        self._corpus = corpus
        self._norm = normalizer

    def compute(self, *, profile_skills: list[str], limit: int = 20) -> SkillGap:
        if not profile_skills:
            return SkillGap(has_profile=False, missing=[])
        have = {self._norm.normalize(s) for s in profile_skills if s and s.strip()}
        have.discard("")
        counter: Counter[str] = Counter()
        n_jobs = 0
        for skills in self._corpus.open_skill_lists():
            n_jobs += 1
            seen = {self._norm.normalize(s) for s in skills if s and s.strip()}
            seen.discard("")
            counter.update(seen)
        total = max(n_jobs, 1)
        missing = [
            SkillGapItem(skill=skill, count=count, pct=round(100.0 * count / total, 1))
            for skill, count in counter.most_common()
            if skill not in have
        ][:limit]
        return SkillGap(has_profile=True, missing=missing)
