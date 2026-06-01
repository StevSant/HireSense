from hiresense.analytics.domain import SkillGapService, SkillNormalizer


class _FakeCorpus:
    def open_skill_lists(self):
        return [["Python", "Kubernetes"], ["python", "k8s"], ["React", "Python"], ["Go"]]


def test_gap_excludes_profile_skills_and_ranks_by_demand():
    svc = SkillGapService(_FakeCorpus(), SkillNormalizer())
    gap = svc.compute(profile_skills=["Python"])
    skills = [g.skill for g in gap.missing]
    # python is in profile → excluded; kubernetes (2, via k8s alias) ranks above react (1)/go (1)
    assert "python" not in skills
    assert skills[0] == "kubernetes"
    top = gap.missing[0]
    assert top.count == 2 and top.pct == 50.0  # 2 of 4 open jobs


def test_no_profile_is_neutral():
    svc = SkillGapService(_FakeCorpus(), SkillNormalizer())
    gap = svc.compute(profile_skills=[])
    assert gap.has_profile is False
    assert gap.missing == []
