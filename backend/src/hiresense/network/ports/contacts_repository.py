from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.network.domain import Contact


class ContactsRepositoryPort(Protocol):
    """Snapshot store for imported LinkedIn connections."""

    def replace_all(self, contacts: list[Contact]) -> int:
        """Replace the whole snapshot (imports are full exports); returns count."""
        ...

    def list_all(self, company: str | None = None) -> list[Contact]:
        """All contacts, optionally filtered by normalized company match."""
        ...

    def find_by_company(self, company_normalized: str) -> list[Contact]: ...

    def count_by_companies(self, companies_normalized: list[str]) -> dict[str, int]:
        """Counts per normalized-company key; keys with zero matches are absent."""
        ...

    def last_imported_at(self) -> datetime | None: ...
