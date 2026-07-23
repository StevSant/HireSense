from __future__ import annotations

from pydantic import BaseModel

from hiresense.analytics.domain.skill_gap_service import SkillGap


class UpskillingStep(BaseModel):
    """A single skill to prioritize, grounded in the current market gap."""

    skill: str
    demand_count: int
    demand_pct: float
    next_action: str


class UpskillingPlan(BaseModel):
    has_profile: bool
    steps: list[UpskillingStep]


class UpskillingPlanService:
    """Turns verified profile skill gaps into a compact, deterministic plan."""

    _ACTIONS = (
        "Learn the core concepts and vocabulary.",
        "Practice the skill in a small, demonstrable project.",
        "Prepare a concrete example you can discuss in an interview.",
    )

    def build(self, skill_gap: SkillGap) -> UpskillingPlan:
        if not skill_gap.has_profile:
            return UpskillingPlan(has_profile=False, steps=[])

        steps = [
            UpskillingStep(
                skill=gap.skill,
                demand_count=gap.count,
                demand_pct=gap.pct,
                next_action=self._ACTIONS[index],
            )
            for index, gap in enumerate(skill_gap.missing[: len(self._ACTIONS)])
        ]
        return UpskillingPlan(has_profile=True, steps=steps)
