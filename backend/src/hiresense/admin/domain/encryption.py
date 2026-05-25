from __future__ import annotations


class EncryptionUnavailableError(RuntimeError):
    """Raised when an encrypt/decrypt is attempted without a configured key."""


class APIKeyCipher:
    """Wraps Fernet for encrypting LLM API keys at rest.

    If `key` is empty, the cipher is in an unavailable state: `encrypt`/`decrypt`
    raise `EncryptionUnavailableError`. Callers can probe `is_available` first
    and fall through to env-based key resolution.
    """

    def __init__(self, key: str) -> None:
        self._key = key.strip()
        self._fernet = None
        if self._key:
            from cryptography.fernet import Fernet

            self._fernet = Fernet(self._key.encode("utf-8"))

    @property
    def is_available(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        if self._fernet is None:
            raise EncryptionUnavailableError(
                "LLM_SETTINGS_ENCRYPTION_KEY is not configured; refuse to store API key."
            )
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        if self._fernet is None:
            raise EncryptionUnavailableError(
                "LLM_SETTINGS_ENCRYPTION_KEY is not configured; cannot decrypt stored key."
            )
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
