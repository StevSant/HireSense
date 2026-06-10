from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hiresense.network.domain import ConnectionsParseError, Contact, NetworkImportService

_HEADER = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"
_ROWS = "Jordan,Lee,https://www.linkedin.com/in/jlee,,Acme Inc.,Engineering Manager,01 Feb 2025\n"
_CSV_BYTES = (_HEADER + "\n" + _ROWS).encode("utf-8")


class _FakeRepo:
    def __init__(self, contacts: list[Contact] | None = None) -> None:
        self._contacts: list[Contact] = contacts or []
        self.replaced: list[Contact] | None = None
        self._imported_at = datetime.now(timezone.utc) if contacts else None

    def replace_all(self, contacts: list[Contact]) -> int:
        self.replaced = contacts
        self._contacts = contacts
        self._imported_at = datetime.now(timezone.utc)
        return len(contacts)

    def list_all(self, company: str | None = None) -> list[Contact]:
        return self._contacts

    def find_by_company(self, company_normalized: str) -> list[Contact]:
        return [c for c in self._contacts if c.company_normalized == company_normalized]

    def count_by_companies(self, companies_normalized: list[str]) -> dict[str, int]:
        return {}

    def last_imported_at(self) -> datetime | None:
        return self._imported_at


@pytest.mark.asyncio
async def test_import_upload_happy_path() -> None:
    repo = _FakeRepo()
    service = NetworkImportService(repository=repo)

    count = await service.import_upload(_CSV_BYTES, filename="Connections.csv")

    assert count == 1
    assert repo.replaced is not None
    assert len(repo.replaced) == 1
    assert repo.replaced[0].first_name == "Jordan"


@pytest.mark.asyncio
async def test_import_upload_propagates_parse_error() -> None:
    repo = _FakeRepo()
    service = NetworkImportService(repository=repo)

    with pytest.raises(ConnectionsParseError):
        await service.import_upload(b"not,a,connections,file\n1,2,3,4\n", filename="x.csv")


@pytest.mark.asyncio
async def test_last_imported_at_returns_none_initially() -> None:
    repo = _FakeRepo()
    service = NetworkImportService(repository=repo)

    result = await service.last_imported_at()

    assert result is None


@pytest.mark.asyncio
async def test_last_imported_at_returns_value_after_import() -> None:
    repo = _FakeRepo()
    service = NetworkImportService(repository=repo)

    await service.import_upload(_CSV_BYTES, filename="Connections.csv")
    result = await service.last_imported_at()

    assert result is not None
