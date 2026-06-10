from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from hiresense.network.domain.connections_parser import parse_connections

if TYPE_CHECKING:
    from hiresense.network.ports import ContactsRepositoryPort


class NetworkImportService:
    """Parses a LinkedIn export upload and replaces the contacts snapshot."""

    def __init__(self, repository: "ContactsRepositoryPort") -> None:
        self._repository = repository

    async def import_upload(self, payload: bytes, *, filename: str) -> int:
        contacts = parse_connections(payload, filename=filename)
        return await asyncio.to_thread(self._repository.replace_all, contacts)

    async def last_imported_at(self) -> datetime | None:
        return await asyncio.to_thread(self._repository.last_imported_at)
