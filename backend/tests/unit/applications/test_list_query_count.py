from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.models import (
    ApplicationCoverLetter,
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
    JobSnapshotSource,
)
from hiresense.applications.infrastructure.repository import ApplicationRepository
from hiresense.infrastructure.database import Base
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.infrastructure import TrackedApplicationOrm


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


class _QueryCounter:
    """Counts SQL statements executed on an engine via the cursor-execute event."""

    def __init__(self, engine) -> None:
        self.count = 0
        event.listen(engine, "before_cursor_execute", self._on)

    def _on(self, conn, cursor, statement, parameters, context, executemany) -> None:
        self.count += 1

    def reset(self) -> None:
        self.count = 0


class _FakeTracking:
    """Returns a fixed tracked list without touching the DB, so the query
    counter observes only the aggregate builder's batch loads."""

    def __init__(self, apps: list[TrackedApplication]) -> None:
        self._apps = apps

    def list(self, status=None, *, limit=None, offset=None) -> list[TrackedApplication]:
        return self._apps


def _seed_app(repo: ApplicationRepository, session_factory) -> TrackedApplication:
    with session_factory() as session:
        orm = TrackedApplicationOrm(
            title="Engineer", company="Acme", status=ApplicationStatus.SAVED.value
        )
        session.add(orm)
        session.commit()
        session.refresh(orm)
        app = TrackedApplication.model_validate(orm)
    repo.create_snapshot(
        ApplicationJobSnapshot(
            application_id=app.id,
            description="desc",
            required_skills=["python"],
            source=JobSnapshotSource.MANUAL.value,
        )
    )
    for score in (0.5, 0.8):  # two matches → latest-of-many exercised
        repo.create_match(
            ApplicationMatch(
                application_id=app.id,
                overall_score=score,
                semantic_score=score,
                skill_score=score,
                experience_score=score,
                language_score=score,
                cv_language="en",
            )
        )
    repo.create_optimization(
        ApplicationCvOptimization(
            application_id=app.id,
            cv_language="en",
            original_tex="o",
            optimized_tex="p",
            improvement_summary="s",
            changes=[],
        )
    )
    repo.create_interview_prep(
        ApplicationInterviewPrep(application_id=app.id, competencies_to_probe=["leadership"])
    )
    repo.create_cover_letter(
        ApplicationCoverLetter(application_id=app.id, body="body", tone="professional")
    )
    return app


def _service(repo: ApplicationRepository, apps: list[TrackedApplication]) -> ApplicationService:
    return ApplicationService(
        repository=repo,
        tracking_service=_FakeTracking(apps),
        ingestion_orchestrator=None,
        skill_extractor=None,
    )


def test_list_query_count_is_constant_regardless_of_application_count(engine, session_factory):
    """The N+1 regression guard: building the list must issue a fixed number of
    queries (one batch per child type), not ~10 per application."""
    repo = ApplicationRepository(session_factory=session_factory)
    apps = [_seed_app(repo, session_factory) for _ in range(4)]

    counter = _QueryCounter(engine)

    counter.reset()
    many = _service(repo, apps).list()
    assert len(many) == 4
    count_for_four = counter.count

    counter.reset()
    one = _service(repo, apps[:1]).list()
    assert len(one) == 1
    count_for_one = counter.count

    # Constant query count: snapshot + matches + optimizations + interview_preps
    # + cover_letters = 5 batch queries, independent of how many applications.
    assert count_for_four == count_for_one == 5

    # The latest-of-many match is still surfaced correctly from the batch.
    assert many[0].latest_match is not None
    assert many[0].match_count == 2
