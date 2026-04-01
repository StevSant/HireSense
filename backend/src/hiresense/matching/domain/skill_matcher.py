from __future__ import annotations

from dataclasses import dataclass, field


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
    ) -> SkillMatchResult:
        if not required_skills:
            return SkillMatchResult(score=1.0)

        candidate_lower = {s.lower() for s in candidate_skills}
        matched: list[str] = []
        missing: list[str] = []

        for skill in required_skills:
            if skill.lower() in candidate_lower:
                matched.append(skill.lower())
            else:
                missing.append(skill.lower())

        score = len(matched) / len(required_skills)

        return SkillMatchResult(
            score=score,
            matched=sorted(matched),
            missing=sorted(missing),
        )
