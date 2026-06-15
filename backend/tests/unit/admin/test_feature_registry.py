from __future__ import annotations

from hiresense.admin.domain.feature_registry import FEATURE_REGISTRY, all_feature_keys, get_feature


def test_all_keys_unique() -> None:
    keys = [f.key for f in FEATURE_REGISTRY]
    assert len(keys) == len(set(keys)), "feature keys must be unique"


def test_lookup_returns_descriptor() -> None:
    desc = get_feature("cv_parser")
    assert desc is not None
    assert desc.name == "CV Parser"


def test_unknown_returns_none() -> None:
    assert get_feature("not_a_real_feature") is None


def test_all_feature_keys_matches_registry() -> None:
    keys = all_feature_keys()
    assert keys == tuple(f.key for f in FEATURE_REGISTRY)


def test_cv_translator_feature_registered() -> None:
    assert "cv_translator" in all_feature_keys()
    feature = get_feature("cv_translator")
    assert feature is not None
    assert feature.name == "CV Translator"
