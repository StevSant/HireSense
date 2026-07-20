from __future__ import annotations

from typing import Protocol


class CompanyProfileSinkPort(Protocol):
    """Where a source adapter records the company profile it already fetched.

    Lets ingestion hand off source-provided company facts (description, website,
    headquarters) without depending on how or where they are stored. Implemented
    in process by the research module's ``CompanyProfileStore``.
    """

    def record(
        self,
        *,
        company_name: str,
        source: str,
        description: str | None = None,
        website: str | None = None,
        headquarters: str | None = None,
    ) -> None: ...
