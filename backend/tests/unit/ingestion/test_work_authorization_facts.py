from __future__ import annotations

import pytest

from hiresense.ingestion.domain.work_authorization_facts import extract_work_authorization_facts
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import InMemoryJobsRepository
from hiresense.kernel.value_objects import SourceType


class _EventBus:
    async def publish(self, event) -> None:  # noqa: ARG002
        pass


class _Source:
    def source_name(self) -> str:
        return "test-source"

    def source_type(self) -> SourceType:
        return SourceType.API

    def supports_snapshot_closure(self) -> bool:
        return False

    async def fetch_jobs(self, filters=None) -> list[RawJobListing]:  # noqa: ARG002
        return [
            RawJobListing(
                source="test-source",
                source_id="job-1",
                raw_data={
                    "description": (
                        "Candidates must be authorized to work in the United States. "
                        "Visa sponsorship is not available for this position."
                    )
                },
            )
        ]


class _Normalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, object]:
        return {
            "title": "Backend Engineer",
            "company": "Acme",
            "description": raw.raw_data["description"],
            "skills": [],
            "location": "US",
            "url": "https://example.test/jobs/1",
        }


@pytest.mark.asyncio
async def test_orchestrator_extracts_explicit_work_authorization_facts() -> None:
    repository = InMemoryJobsRepository()
    orchestrator = IngestionOrchestrator(
        sources=[_Source()],
        normalizers={"test-source": _Normalizer()},
        event_bus=_EventBus(),
        repository=repository,
        cooldown_seconds=0,
    )

    await orchestrator.run()

    job = repository.list_all()[0]
    assert job.requires_existing_work_authorization is True
    assert job.visa_sponsorship_available is False


@pytest.mark.parametrize(
    ("description", "requires_existing_authorization", "sponsorship_available"),
    [
        ("Visa sponsorship is available for this role.", None, True),
        ("Applicants must have current work authorization.", True, None),
        ("We welcome candidates who may need sponsorship.", None, None),
        ("", None, None),
    ],
)
def test_extraction_only_returns_explicit_work_authorization_facts(
    description: str,
    requires_existing_authorization: bool | None,
    sponsorship_available: bool | None,
) -> None:
    facts = extract_work_authorization_facts(description)

    assert facts.requires_existing_work_authorization is requires_existing_authorization
    assert facts.visa_sponsorship_available is sponsorship_available
