from __future__ import annotations

import base64
import hashlib
import secrets

# scrypt cost parameters. n*r*128 bytes of memory (here 16 MiB), which stays
# under scrypt's default 32 MiB maxmem cap while remaining expensive to brute
# force. Encoded into the hash string so stored hashes remain verifiable even
# if these defaults change later.
_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_SCHEME = "scrypt"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii"))


def hash_password(password: str, *, n: int = _SCRYPT_N, r: int = _SCRYPT_R, p: int = _SCRYPT_P) -> str:
    """Hash a plaintext password into a self-describing scrypt string.

    Format: ``scrypt$n$r$p$<salt_b64>$<hash_b64>``. Generate a value for
    AUTH_PASSWORD_HASH with:

        python -c "from hiresense.identity.domain import hash_password; print(hash_password('your-password'))"
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
    return f"{_SCHEME}${n}${r}${p}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verify a plaintext password against a scrypt hash string.

    Returns False (never raises) on any malformed or unsupported hash so a
    corrupt credential can't be distinguished by timing or exception behaviour.
    """
    try:
        scheme, n_str, r_str, p_str, salt_b64, hash_b64 = encoded.split("$")
        if scheme != _SCHEME:
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(hash_b64)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_str),
            r=int(r_str),
            p=int(p_str),
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(derived, expected)
