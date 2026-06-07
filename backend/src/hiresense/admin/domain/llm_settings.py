from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LLMSettingsRecord:
    """Domain view of the single global LLM settings row.

    Pure value object — the persisted shape mapped out of the ORM by the
    repository. `api_key_encrypted` carries the Fernet ciphertext (never the
    plaintext); decryption happens in the domain services via the cipher.
    """

    provider: str
    model: str
    api_key_encrypted: str | None
    extra_params: dict = field(default_factory=dict)
    updated_by: str | None = None
    updated_at: datetime | None = None
