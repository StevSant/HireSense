"""Tests for dedicated prerank weight settings (Work Unit A).

These tests are intentionally written BEFORE the implementation (TDD RED phase).
They verify REQ-06: prerank weights come from Settings, not hardcoded constants.
"""

from __future__ import annotations

import pytest


def _make_settings(monkeypatch: pytest.MonkeyPatch) -> object:
    """Build a Settings instance with the minimum required env vars."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    # Reimport so pydantic_settings picks up the patched env.
    import importlib
    import hiresense.config

    importlib.reload(hiresense.config)
    return hiresense.config.Settings()


def test_settings_has_prerank_weight_skill_default_0_4(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must expose prerank_weight_skill with default 0.4."""
    settings = _make_settings(monkeypatch)
    assert hasattr(settings, "prerank_weight_skill")
    assert abs(settings.prerank_weight_skill - 0.4) < 1e-9


def test_settings_has_prerank_weight_semantic_default_0_6(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must expose prerank_weight_semantic with default 0.6."""
    settings = _make_settings(monkeypatch)
    assert hasattr(settings, "prerank_weight_semantic")
    assert abs(settings.prerank_weight_semantic - 0.6) < 1e-9


def test_settings_has_prerank_top_k_cap_default_2000(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must expose prerank_top_k_cap with default 2000."""
    settings = _make_settings(monkeypatch)
    assert hasattr(settings, "prerank_top_k_cap")
    assert settings.prerank_top_k_cap == 2000


def test_prerank_weights_are_distinct_from_matching_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prerank weights are separate fields from the 10-dim matching weights.

    weight_skill_match and weight_semantic are int percentages for the deep
    matching engine; prerank_weight_skill / prerank_weight_semantic are
    dedicated floats for the pre-ranking blend. They must not alias each other.
    """
    settings = _make_settings(monkeypatch)
    # Matching weights are integers (percentage units: 20, 15)
    assert isinstance(settings.weight_skill_match, int)
    assert isinstance(settings.weight_semantic, int)
    # Prerank weights are floats
    assert isinstance(settings.prerank_weight_skill, float)
    assert isinstance(settings.prerank_weight_semantic, float)


def test_prerank_weight_skill_overridable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """PRERANK_WEIGHT_SKILL env var overrides the default."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PRERANK_WEIGHT_SKILL", "0.3")
    monkeypatch.setenv("PRERANK_WEIGHT_SEMANTIC", "0.7")
    import importlib
    import hiresense.config

    importlib.reload(hiresense.config)
    settings = hiresense.config.Settings()
    assert abs(settings.prerank_weight_skill - 0.3) < 1e-9
    assert abs(settings.prerank_weight_semantic - 0.7) < 1e-9
