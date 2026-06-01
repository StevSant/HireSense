from hiresense.analytics.domain import SkillNormalizer


def test_lowercases_and_trims():
    assert SkillNormalizer().normalize("  Python  ") == "python"


def test_applies_aliases():
    n = SkillNormalizer()
    assert n.normalize("React.js") == "react"
    assert n.normalize("ReactJS") == "react"
    assert n.normalize("k8s") == "kubernetes"
    assert n.normalize("JS") == "javascript"


def test_empty_is_empty():
    assert SkillNormalizer().normalize("   ") == ""
