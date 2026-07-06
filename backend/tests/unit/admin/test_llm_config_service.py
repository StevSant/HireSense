from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet

from hiresense.admin.domain.encryption import APIKeyCipher
from hiresense.admin.domain.llm_config_service import LLMConfigService


@dataclass
class _FakeSettingsRow:
    provider: str
    model: str
    api_key_encrypted: str | None
    extra_params: dict


@dataclass
class _FakeOverrideRow:
    feature_key: str
    provider: str | None
    model: str | None
    extra_params: dict


class _SettingsRepo:
    def __init__(self, row: _FakeSettingsRow | None) -> None:
        self._row = row

    def get(self) -> _FakeSettingsRow | None:
        return self._row


class _OverrideRepo:
    def __init__(self, overrides: dict[str, _FakeOverrideRow]) -> None:
        self._overrides = overrides

    def get(self, feature_key: str) -> _FakeOverrideRow | None:
        return self._overrides.get(feature_key)


def _service(settings_row, overrides, cipher: APIKeyCipher) -> LLMConfigService:
    return LLMConfigService(
        settings_repo=_SettingsRepo(settings_row),
        override_repo=_OverrideRepo(overrides),
        cipher=cipher,
        env_provider="anthropic",
        env_model="claude-sonnet-4-6",
        env_api_key="env-key",
    )


def test_resolves_from_env_when_no_global_row() -> None:
    svc = _service(None, {}, APIKeyCipher(""))
    config = svc.resolve("cv_parser")
    assert config.provider == "anthropic"
    assert config.model == "claude-sonnet-4-6"
    assert config.api_key == "env-key"
    assert config.source == "env"


def test_resolves_from_global_row_with_decrypted_key() -> None:
    key = Fernet.generate_key().decode()
    cipher = APIKeyCipher(key)
    encrypted = cipher.encrypt("real-api-key")
    row = _FakeSettingsRow(
        provider="openai", model="gpt-4o-mini", api_key_encrypted=encrypted, extra_params={}
    )
    svc = _service(row, {}, cipher)
    config = svc.resolve("cv_parser")
    assert config.provider == "openai"
    assert config.model == "gpt-4o-mini"
    assert config.api_key == "real-api-key"
    assert config.source == "global"


def test_falls_back_to_env_when_global_has_no_key() -> None:
    row = _FakeSettingsRow(
        provider="openai", model="gpt-4o-mini", api_key_encrypted=None, extra_params={}
    )
    svc = _service(row, {}, APIKeyCipher(""))
    config = svc.resolve("cv_parser")
    assert config.api_key == "env-key"
    assert config.provider == "openai"  # provider/model still come from the global row


def test_override_provider_only_inherits_model() -> None:
    row = _FakeSettingsRow(
        provider="anthropic", model="claude-sonnet-4-6", api_key_encrypted=None, extra_params={}
    )
    overrides = {
        "cv_parser": _FakeOverrideRow(
            feature_key="cv_parser",
            provider="openai",
            model=None,
            extra_params={},
        )
    }
    svc = _service(row, overrides, APIKeyCipher(""))
    config = svc.resolve("cv_parser")
    assert config.provider == "openai"
    assert config.model == "claude-sonnet-4-6"  # inherits
    assert config.source == "override"


def test_override_model_only_inherits_provider() -> None:
    row = _FakeSettingsRow(
        provider="anthropic", model="claude-sonnet-4-6", api_key_encrypted=None, extra_params={}
    )
    overrides = {
        "cv_parser": _FakeOverrideRow(
            feature_key="cv_parser",
            provider=None,
            model="claude-haiku-4-5",
            extra_params={},
        )
    }
    svc = _service(row, overrides, APIKeyCipher(""))
    config = svc.resolve("cv_parser")
    assert config.provider == "anthropic"  # inherits
    assert config.model == "claude-haiku-4-5"


def test_extra_params_merge_override_wins() -> None:
    row = _FakeSettingsRow(
        provider="anthropic",
        model="claude-sonnet-4-6",
        api_key_encrypted=None,
        extra_params={"temperature": 0.2, "max_tokens": 1024},
    )
    overrides = {
        "cv_parser": _FakeOverrideRow(
            feature_key="cv_parser",
            provider=None,
            model=None,
            extra_params={"temperature": 0.0},
        )
    }
    svc = _service(row, overrides, APIKeyCipher(""))
    config = svc.resolve("cv_parser")
    assert config.extra_params == {"temperature": 0.0, "max_tokens": 1024}


def test_other_feature_unaffected_by_override() -> None:
    row = _FakeSettingsRow(
        provider="anthropic", model="claude-sonnet-4-6", api_key_encrypted=None, extra_params={}
    )
    overrides = {
        "cv_parser": _FakeOverrideRow(
            feature_key="cv_parser",
            provider="openai",
            model="gpt-4o-mini",
            extra_params={},
        )
    }
    svc = _service(row, overrides, APIKeyCipher(""))
    cv = svc.resolve("cv_parser")
    other = svc.resolve("culture_scorer")
    assert cv.provider == "openai"
    assert other.provider == "anthropic"


def test_invalidate_clears_cache() -> None:
    """After invalidate(), the next resolve() must re-read the repos."""
    state = {"row": None}

    class _DynamicRepo:
        def get(self):
            return state["row"]

    class _NoOverrides:
        def get(self, _key):
            return None

    svc = LLMConfigService(
        settings_repo=_DynamicRepo(),
        override_repo=_NoOverrides(),
        cipher=APIKeyCipher(""),
        env_provider="anthropic",
        env_model="env-model",
        env_api_key="env-key",
    )
    first = svc.resolve("cv_parser")
    assert first.model == "env-model"

    state["row"] = _FakeSettingsRow(
        provider="openai",
        model="new-model",
        api_key_encrypted=None,
        extra_params={},
    )
    # Without invalidate, cache hides the change:
    cached = svc.resolve("cv_parser")
    assert cached.model == "env-model"
    svc.invalidate()
    fresh = svc.resolve("cv_parser")
    assert fresh.model == "new-model"
