from __future__ import annotations

from dataclasses import dataclass

from hiresense.admin.domain.resolved_config import ResolvedConfig


@dataclass(frozen=True)
class EffectiveFeatureConfig:
    """View-model: a feature's effective config with provenance for the admin UI."""

    feature_key: str
    feature_name: str
    feature_description: str
    provider: str
    model: str
    inherits_provider: bool
    inherits_model: bool
    extra_params: dict
    source: str  # "inherited" if both inherit_*; "override" otherwise

    @classmethod
    def from_resolution(
        cls,
        *,
        feature_key: str,
        feature_name: str,
        feature_description: str,
        resolved: ResolvedConfig,
        override_provider: str | None,
        override_model: str | None,
        extra_params: dict,
    ) -> "EffectiveFeatureConfig":
        inherits_provider = override_provider is None
        inherits_model = override_model is None
        source = (
            "inherited"
            if (inherits_provider and inherits_model and not extra_params)
            else "override"
        )
        return cls(
            feature_key=feature_key,
            feature_name=feature_name,
            feature_description=feature_description,
            provider=resolved.provider,
            model=resolved.model,
            inherits_provider=inherits_provider,
            inherits_model=inherits_model,
            extra_params=extra_params,
            source=source,
        )
