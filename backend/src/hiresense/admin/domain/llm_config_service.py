from __future__ import annotations

import logging
import threading
import time

from hiresense.admin.domain.encryption import APIKeyCipher, EncryptionUnavailableError
from hiresense.admin.domain.resolved_config import ResolvedConfig
from hiresense.admin.ports import LLMFeatureOverrideRepositoryPort, LLMSettingsRepositoryPort

logger = logging.getLogger(__name__)

# Feature keys whose output is a short verdict — a label, a confidence score,
# a brief extraction — rather than long-form or batched generation. These get
# the smaller `llm_classifier_max_tokens` default instead of
# `llm_default_max_tokens`. match_quick_scorer is deliberately NOT included
# here even though it "classifies": it returns batched per-job JSON for up to
# match_quick_batch_size jobs in a single call, so it needs the larger default
# to avoid truncating the tail of the batch.
CLASSIFIER_FEATURE_KEYS: frozenset[str] = frozenset(
    {
        "inbox-classification",
        "job_quality_classifier",
        "application_skill_extractor",
        "preference_explanation",
    }
)


class LLMConfigService:
    """Resolves the effective LLM config for any feature_key.

    Resolution order: feature_override → global llm_settings row → .env fallback.
    A short in-memory TTL cache (~30s) avoids hammering the DB for every call;
    the cache is invalidated explicitly after a successful PUT.
    """

    _CACHE_TTL_SECONDS = 30.0

    def __init__(
        self,
        *,
        settings_repo: LLMSettingsRepositoryPort,
        override_repo: LLMFeatureOverrideRepositoryPort,
        cipher: APIKeyCipher,
        env_provider: str,
        env_model: str,
        env_api_key: str,
        feature_default_models: dict[str, str] | None = None,
        default_max_tokens: int = 2048,
        classifier_max_tokens: int = 512,
    ) -> None:
        self._settings_repo = settings_repo
        self._override_repo = override_repo
        self._cipher = cipher
        self._env_provider = env_provider
        self._env_model = env_model
        self._env_api_key = env_api_key
        # Injected as ints from bootstrap (which reads config) so this domain
        # class never imports the settings module directly.
        self._default_max_tokens = default_max_tokens
        self._classifier_max_tokens = classifier_max_tokens
        # Per-feature default model used only when there is no admin override
        # and no global settings row (i.e. the .env fallback path). Lets a
        # feature ship with a different default model than the global env one
        # (e.g. a cheap model for the quick scorer) while still letting the
        # admin override it. Keys are feature_keys.
        self._feature_default_models = feature_default_models or {}
        self._cache: dict[str, tuple[float, ResolvedConfig]] = {}
        self._lock = threading.Lock()

    # ---- Resolution ---------------------------------------------------

    def resolve(self, feature_key: str) -> ResolvedConfig:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(feature_key)
            if cached and now - cached[0] < self._CACHE_TTL_SECONDS:
                return cached[1]

        resolved = self._resolve_fresh(feature_key)
        with self._lock:
            self._cache[feature_key] = (now, resolved)
        return resolved

    def _resolve_fresh(self, feature_key: str) -> ResolvedConfig:
        global_row = self._settings_repo.get()
        override = self._override_repo.get(feature_key)

        if global_row is not None:
            provider = global_row.provider
            model = global_row.model
            extra_params = dict(global_row.extra_params or {})
            api_key = self._decrypt_or_env_fallback(global_row.api_key_encrypted)
            source = "global"
        else:
            provider = self._env_provider
            model = self._feature_default_models.get(feature_key, self._env_model)
            api_key = self._env_api_key
            extra_params = {}
            source = "env"

        if override is not None:
            if override.provider is not None:
                provider = override.provider
                source = "override"
            if override.model is not None:
                model = override.model
                source = "override"
            override_params = dict(override.extra_params or {})
            if override_params:
                extra_params = {**extra_params, **override_params}
                source = "override"

        # Inject a default output token cap only when nobody (global settings
        # row or feature override) has already set one — an explicit
        # admin-set max_tokens always wins.
        if "max_tokens" not in extra_params:
            default = (
                self._classifier_max_tokens
                if feature_key in CLASSIFIER_FEATURE_KEYS
                else self._default_max_tokens
            )
            extra_params = {**extra_params, "max_tokens": default}

        return ResolvedConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            extra_params=extra_params,
            source=source,
        )

    def _decrypt_or_env_fallback(self, ciphertext: str | None) -> str:
        if not ciphertext:
            return self._env_api_key
        if not self._cipher.is_available:
            logger.warning(
                "llm_settings has encrypted api_key but LLM_SETTINGS_ENCRYPTION_KEY is unset; "
                "falling back to env."
            )
            return self._env_api_key
        try:
            return self._cipher.decrypt(ciphertext)
        except (EncryptionUnavailableError, Exception) as exc:
            logger.warning("failed to decrypt stored api_key (%s); falling back to env.", exc)
            return self._env_api_key

    # ---- Cache management --------------------------------------------

    def invalidate(self) -> None:
        """Drop all cached configs. Call after any settings/override write."""
        with self._lock:
            self._cache.clear()
