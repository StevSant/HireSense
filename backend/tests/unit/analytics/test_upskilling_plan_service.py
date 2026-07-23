from hiresense.analytics.domain.skill_gap_service import SkillGap, SkillGapItem
from hiresense.analytics.domain.upskilling_plan_service import UpskillingPlanService


def test_plan_prioritizes_the_highest_demand_verified_skill_gaps() -> None:
    plan = UpskillingPlanService().build(
        SkillGap(
            has_profile=True,
            missing=[
                SkillGapItem(skill="kubernetes", count=12, pct=60.0),
                SkillGapItem(skill="react", count=8, pct=40.0),
                SkillGapItem(skill="go", count=4, pct=20.0),
                SkillGapItem(skill="terraform", count=2, pct=10.0),
            ],
        )
    )

    assert plan.has_profile is True
    assert [step.skill for step in plan.steps] == ["kubernetes", "react", "go"]
    assert plan.steps[0].demand_count == 12
    assert plan.steps[0].demand_pct == 60.0
    assert plan.steps[0].next_action == "Learn the core concepts and vocabulary."
    assert plan.steps[1].next_action == "Practice the skill in a small, demonstrable project."


def test_plan_is_empty_when_a_profile_has_not_been_verified() -> None:
    plan = UpskillingPlanService().build(SkillGap(has_profile=False, missing=[]))

    assert plan.has_profile is False
    assert plan.steps == []
