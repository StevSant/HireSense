from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from hiresense.admin.domain.encryption import APIKeyCipher, EncryptionUnavailableError


def test_round_trip_succeeds_with_valid_key() -> None:
    cipher = APIKeyCipher(Fernet.generate_key().decode())
    plaintext = "sk-anthropic-abc123-do-not-leak"
    encrypted = cipher.encrypt(plaintext)
    assert encrypted != plaintext
    assert cipher.decrypt(encrypted) == plaintext


def test_empty_key_makes_cipher_unavailable() -> None:
    cipher = APIKeyCipher("")
    assert cipher.is_available is False
    with pytest.raises(EncryptionUnavailableError):
        cipher.encrypt("anything")


def test_decrypt_with_wrong_key_raises() -> None:
    a = APIKeyCipher(Fernet.generate_key().decode())
    b = APIKeyCipher(Fernet.generate_key().decode())
    ciphertext = a.encrypt("payload")
    with pytest.raises(Exception):
        b.decrypt(ciphertext)
