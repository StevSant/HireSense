from __future__ import annotations

import re
from dataclasses import dataclass, field

from hiresense.kernel import normalize_skill


@dataclass
class SkillMatchResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


class SkillMatcher:
    def match(
        self,
        candidate_skills: list[str],
        required_skills: list[str],
        evidence_text: str | None = None,
        inferred_present: list[str] | None = None,
    ) -> SkillMatchResult:
        if not required_skills:
            return SkillMatchResult(score=1.0)

        candidate_canonical = {normalize_skill(s) for s in candidate_skills}
        inferred_canonical = {normalize_skill(s) for s in (inferred_present or [])}
        evidence = (evidence_text or "").lower()

        matched: set[str] = set()
        missing: set[str] = set()

        for skill in required_skills:
            canonical = normalize_skill(skill)
            if not canonical:
                continue
            if (
                canonical in candidate_canonical
                or canonical in inferred_canonical
                or self._evidenced(canonical, evidence)
            ):
                matched.add(canonical)
            else:
                missing.add(canonical)

        total = len(matched) + len(missing)
        score = len(matched) / total if total else 1.0

        return SkillMatchResult(
            score=score,
            matched=sorted(matched),
            missing=sorted(missing),
        )

    @staticmethod
    def _evidenced(canonical: str, evidence: str) -> bool:
        if not evidence:
            return False
        # Word-boundary match so "java" is not satisfied by "javascript".
        return re.search(rf"\b{re.escape(canonical)}\b", evidence) is not None
