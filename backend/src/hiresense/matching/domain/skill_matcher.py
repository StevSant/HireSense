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
        matches = re.finditer(rf"\b{re.escape(canonical)}\b", evidence)
        return any(
            not SkillMatcher._is_negated_evidence(evidence, match.start(), match.end())
            for match in matches
        )

    @staticmethod
    def _is_negated_evidence(evidence: str, start: int, end: int) -> bool:
        before = evidence[max(0, start - 80) : start]
        after = evidence[end : min(len(evidence), end + 60)]
        return bool(
            re.search(
                r"\b(?:no|without)\s+(?:professional\s+)?"
                r"(?:experience|knowledge|exposure|background|proficiency|skills?)?\s*"
                r"(?:with|in)?\s*$",
                before,
            )
            or re.match(
                r"\s*(?:experience|knowledge|exposure|background|proficiency|skills?)?\s*"
                r"(?:is|was|were)?\s*(?:none|absent|lacking)\b",
                after,
            )
            or re.search(
                r"\b(?:never|haven't|hasn't|didn't|doesn't|don't)\s+"
                r"(?:used|worked\s+(?:with|on)|had\s+experience\s+with)\s*$",
                before,
            )
            or re.search(r"\bnot\s+(?:experienced|proficient|familiar)\s+(?:with|in)?\s*$", before)
        )
