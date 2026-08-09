"""A stored LLM API key that cannot be decrypted is silently replaced by the
environment key. That is a credential swap — corrupted ciphertext, a rotated
encryption secret, or a tampered DB row all take effect with no audit trail
unless the fallback says so out loud.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet

from hiresense.admin.domain.encryption import APIKeyCipher
from hiresense.admin.domain.llm_settings_service import LLMSettingsService

_LOGGER_NAME = "hiresense.admin.domain.llm_settings_service"

# Long enough that mask_api_key keeps the last 4 chars, so the two keys stay
# distinguishable through the masked view.
_ENV_KEY = "sk-0000000000000envv"
_STORED_KEY = "sk-1111111111111ored"


class _Row:
    def __init__(self, api_key_encrypted: str) -> None:
        self.provider = "anthropic"
        self.model = "claude-sonnet-5"
        self.api_key_encrypted = api_key_encrypted
        self.extra_params: dict = {}
        self.updated_by = "admin"
        self.updated_at = None


class _SettingsRepo:
    def __init__(self, row: _Row | None) -> None:
        self._row = row

    def get(self) -> _Row | None:
        return self._row


class _Unused:
    """Stands in for the collaborators this path never reaches."""

    def __getattr__(self, name: str):
        raise AssertionError(f"unexpected call to {name}")


def _service(*, ciphertext: str, cipher: APIKeyCipher, env_api_key: str) -> LLMSettingsService:
    return LLMSettingsService(
        settings_repo=_SettingsRepo(_Row(ciphertext)),
        override_repo=_Unused(),
        audit_repo=_Unused(),
        cipher=cipher,
        config_service=_Unused(),
        factory=_Unused(),
        test_runner=_Unused(),
        env_provider="anthropic",
        env_model="claude-sonnet-5",
        env_api_key=env_api_key,
    )


def test_undecryptable_stored_key_is_logged_before_falling_back(caplog) -> None:
    # A valid cipher, but the stored value was encrypted with a different key —
    # exactly what a rotated encryption secret looks like.
    other_key_ciphertext = Fernet(Fernet.generate_key()).encrypt(_STORED_KEY.encode()).decode()
    service = _service(
        ciphertext=other_key_ciphertext,
        cipher=APIKeyCipher(Fernet.generate_key().decode()),
        env_api_key=_ENV_KEY,
    )

    with caplog.at_level(logging.ERROR, logger=_LOGGER_NAME):
        view = service.get_global_view()

    # Fallback behavior is unchanged: the env key is what gets used...
    assert view.api_key_mask.endswith("envv")
    # ...but it is no longer invisible.
    records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert records, "an undecryptable stored key must be logged, not swallowed"
    message = records[0].getMessage()
    assert "decrypt" in message
    assert records[0].exc_info is not None


def test_log_never_leaks_the_ciphertext_or_either_key(caplog) -> None:
    other_key_ciphertext = Fernet(Fernet.generate_key()).encrypt(_STORED_KEY.encode()).decode()
    service = _service(
        ciphertext=other_key_ciphertext,
        cipher=APIKeyCipher(Fernet.generate_key().decode()),
        env_api_key=_ENV_KEY,
    )

    with caplog.at_level(logging.ERROR, logger=_LOGGER_NAME):
        service.get_global_view()

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert other_key_ciphertext not in logged
    assert _ENV_KEY not in logged


def test_no_encryption_key_configured_stays_quiet(caplog) -> None:
    """An unconfigured cipher is a declared degraded state, not a failure — it
    must not be reported as an error on every read."""
    service = _service(
        ciphertext="whatever",
        cipher=APIKeyCipher(""),
        env_api_key=_ENV_KEY,
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        view = service.get_global_view()

    assert view.api_key_mask.endswith("envv")
    assert caplog.records == []


def test_successful_decryption_is_not_logged(caplog) -> None:
    key = Fernet.generate_key().decode()
    cipher = APIKeyCipher(key)
    service = _service(
        ciphertext=cipher.encrypt(_STORED_KEY),
        cipher=cipher,
        env_api_key=_ENV_KEY,
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        view = service.get_global_view()

    assert view.api_key_mask.endswith("ored")
    assert caplog.records == []
