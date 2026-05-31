from __future__ import annotations

from dataclasses import dataclass

from hiresense.admin.domain.effective_config import EffectiveFeatureConfig
from hiresense.admin.domain.encryption import APIKeyCipher, EncryptionUnavailableError
from hiresense.admin.domain.feature_registry import FEATURE_REGISTRY
from hiresense.admin.domain.llm_config_service import LLMConfigService
from hiresense.admin.domain.masking import mask_api_key
from hiresense.admin.domain.resolved_config import ResolvedConfig
from hiresense.admin.domain.test_result import TestResult
from hiresense.admin.ports import (
    LLMAuditLogRepositoryPort,
    LLMFactoryPort,
    LLMFeatureOverrideRepositoryPort,
    LLMSettingsRepositoryPort,
    LLMTestRunnerPort,
)


class LLMSettingsServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class GlobalSettingsView:
    provider: str
    model: str
    api_key_mask: str
    has_stored_key: bool
    extra_params: dict
    updated_by: str | None
    updated_at_iso: str | None
    source: str  # "global" if DB row, "env" if falling back


class LLMSettingsService:
    """Command + query service for the admin LLM settings endpoints.

    Holds no state itself — wraps the repos, the cipher, and the test runner.
    Responsible for: masked reads, validated writes, audit logging, and
    invalidating the per-feature config cache after any mutation.
    """

    def __init__(
        self,
        *,
        settings_repo: LLMSettingsRepositoryPort,
        override_repo: LLMFeatureOverrideRepositoryPort,
        audit_repo: LLMAuditLogRepositoryPort,
        cipher: APIKeyCipher,
        config_service: LLMConfigService,
        factory: LLMFactoryPort,
        test_runner: LLMTestRunnerPort,
        env_provider: str,
        env_model: str,
        env_api_key: str,
    ) -> None:
        self._settings_repo = settings_repo
        self._override_repo = override_repo
        self._audit_repo = audit_repo
        self._cipher = cipher
        self._config_service = config_service
        self._factory = factory
        self._test_runner = test_runner
        self._env_provider = env_provider
        self._env_model = env_model
        self._env_api_key = env_api_key

    # ---- Global config -----------------------------------------------

    def get_global_view(self) -> GlobalSettingsView:
        row = self._settings_repo.get()
        if row is None:
            return GlobalSettingsView(
                provider=self._env_provider,
                model=self._env_model,
                api_key_mask=mask_api_key(self._env_api_key),
                has_stored_key=False,
                extra_params={},
                updated_by=None,
                updated_at_iso=None,
                source="env",
            )
        api_key_plain = self._safe_decrypt(row.api_key_encrypted)
        return GlobalSettingsView(
            provider=row.provider,
            model=row.model,
            api_key_mask=mask_api_key(api_key_plain),
            has_stored_key=bool(row.api_key_encrypted),
            extra_params=dict(row.extra_params or {}),
            updated_by=row.updated_by,
            updated_at_iso=row.updated_at.isoformat() if row.updated_at else None,
            source="global",
        )

    async def test_global_config(
        self,
        *,
        provider: str,
        model: str,
        api_key: str | None,
        extra_params: dict | None,
    ) -> TestResult:
        effective_key = api_key if api_key else self._current_global_key_or_env()
        if not effective_key:
            return TestResult(success=False, latency_ms=0.0, response_preview="", error="no api_key available")
        config = ResolvedConfig(
            provider=provider,
            model=model,
            api_key=effective_key,
            extra_params=extra_params or {},
            source="test",
        )
        return await self._test_runner.run(config)

    async def update_global_config(
        self,
        *,
        provider: str,
        model: str,
        api_key: str | None,
        extra_params: dict | None,
        actor: str | None,
        skip_test: bool = False,
    ) -> GlobalSettingsView:
        if not skip_test:
            result = await self.test_global_config(
                provider=provider, model=model, api_key=api_key, extra_params=extra_params,
            )
            if not result.success:
                raise LLMSettingsServiceError(f"test call failed: {result.error}")

        if api_key is not None:
            if not self._cipher.is_available:
                raise LLMSettingsServiceError(
                    "LLM_SETTINGS_ENCRYPTION_KEY is not configured; cannot persist new api_key."
                )
            api_key_encrypted: str | None = self._cipher.encrypt(api_key)
        else:
            api_key_encrypted = None  # repo treats None as "leave existing untouched"

        before = self._settings_repo.get()
        before_summary = {
            "provider": before.provider if before else None,
            "model": before.model if before else None,
            "extra_params": dict(before.extra_params) if before else None,
        }

        self._settings_repo.upsert(
            provider=provider,
            model=model,
            api_key_encrypted=api_key_encrypted,
            extra_params=extra_params or {},
            updated_by=actor,
        )
        self._config_service.invalidate()
        self._factory.invalidate()

        after_summary = {
            "provider": provider,
            "model": model,
            "extra_params": extra_params or {},
            "api_key_rotated": api_key is not None,
        }
        self._audit_repo.append(
            actor=actor,
            action="update_global",
            target="llm_settings",
            changes={"before": before_summary, "after": after_summary},
        )
        return self.get_global_view()

    # ---- Feature overrides -------------------------------------------

    def list_effective_features(self) -> list[EffectiveFeatureConfig]:
        result: list[EffectiveFeatureConfig] = []
        for descriptor in FEATURE_REGISTRY:
            resolved = self._config_service.resolve(descriptor.key)
            override = self._override_repo.get(descriptor.key)
            result.append(
                EffectiveFeatureConfig.from_resolution(
                    feature_key=descriptor.key,
                    feature_name=descriptor.name,
                    feature_description=descriptor.description,
                    resolved=resolved,
                    override_provider=override.provider if override else None,
                    override_model=override.model if override else None,
                    extra_params=dict(override.extra_params) if override else {},
                )
            )
        return result

    async def test_override(
        self,
        *,
        feature_key: str,
        provider: str | None,
        model: str | None,
        extra_params: dict | None,
    ) -> TestResult:
        base = self._config_service.resolve(feature_key)
        merged_extras = {**base.extra_params, **(extra_params or {})}
        candidate = ResolvedConfig(
            provider=provider or base.provider,
            model=model or base.model,
            api_key=base.api_key,
            extra_params=merged_extras,
            source="test",
        )
        if not candidate.api_key:
            return TestResult(
                success=False, latency_ms=0.0, response_preview="",
                error="provider has no api_key configured; set the global key first",
            )
        return await self._test_runner.run(candidate)

    async def set_override(
        self,
        *,
        feature_key: str,
        provider: str | None,
        model: str | None,
        extra_params: dict | None,
        actor: str | None,
        skip_test: bool = False,
    ) -> EffectiveFeatureConfig:
        if not skip_test and (provider is not None or model is not None):
            result = await self.test_override(
                feature_key=feature_key, provider=provider, model=model, extra_params=extra_params,
            )
            if not result.success:
                raise LLMSettingsServiceError(f"override test failed: {result.error}")

        before = self._override_repo.get(feature_key)
        self._override_repo.upsert(
            feature_key=feature_key,
            provider=provider,
            model=model,
            extra_params=extra_params or {},
            updated_by=actor,
        )
        self._config_service.invalidate()

        self._audit_repo.append(
            actor=actor,
            action="set_override",
            target=feature_key,
            changes={
                "before": {
                    "provider": before.provider if before else None,
                    "model": before.model if before else None,
                    "extra_params": dict(before.extra_params) if before else None,
                } if before else None,
                "after": {
                    "provider": provider,
                    "model": model,
                    "extra_params": extra_params or {},
                },
            },
        )
        return self._effective_for(feature_key)

    def clear_override(self, *, feature_key: str, actor: str | None) -> EffectiveFeatureConfig:
        deleted = self._override_repo.delete(feature_key)
        self._config_service.invalidate()
        self._audit_repo.append(
            actor=actor,
            action="clear_override",
            target=feature_key,
            changes={"deleted": deleted},
        )
        return self._effective_for(feature_key)

    # ---- Internal helpers -------------------------------------------

    def _effective_for(self, feature_key: str) -> EffectiveFeatureConfig:
        for view in self.list_effective_features():
            if view.feature_key == feature_key:
                return view
        raise LLMSettingsServiceError(f"unknown feature_key: {feature_key}")

    def _safe_decrypt(self, ciphertext: str | None) -> str:
        if not ciphertext or not self._cipher.is_available:
            return self._env_api_key
        try:
            return self._cipher.decrypt(ciphertext)
        except EncryptionUnavailableError:
            return self._env_api_key
        except Exception:
            return self._env_api_key

    def _current_global_key_or_env(self) -> str:
        row = self._settings_repo.get()
        if row is None or not row.api_key_encrypted:
            return self._env_api_key
        return self._safe_decrypt(row.api_key_encrypted)
