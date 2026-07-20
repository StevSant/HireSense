from __future__ import annotations


import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
from hiresense.tracking.domain.models import ApplicationStatus
from hiresense.tracking.infrastructure import TrackedApplicationOrm


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture()
def repo(session_factory):
    return ApplicationRepository(session_factory=session_factory)


@pytest.fixture()
def tracked_app(session_factory) -> TrackedApplicationOrm:
    with session_factory() as session:
        app = TrackedApplicationOrm(
            title="Software Engineer",
            company="Fieldguide",
            status=ApplicationStatus.SAVED.value,
        )
        session.add(app)
        session.commit()
        session.refresh(app)
        return app


def test_create_and_get_snapshot(repo, tracked_app):
    snap = ApplicationJobSnapshot(
        application_id=tracked_app.id,
        description="job desc",
        required_skills=["python"],
        source=JobSnapshotSource.MANUAL.value,
    )
    created = repo.create_snapshot(snap)
    fetched = repo.get_snapshot(tracked_app.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.required_skills == ["python"]


def test_create_and_get_latest_match(repo, tracked_app):
    m1 = ApplicationMatch(
        application_id=tracked_app.id,
        overall_score=0.5,
        semantic_score=0.5,
        skill_score=0.5,
        experience_score=0.5,
        language_score=0.5,
        cv_language="en",
    )
    m2 = ApplicationMatch(
        application_id=tracked_app.id,
        overall_score=0.8,
        semantic_score=0.8,
        skill_score=0.8,
        experience_score=0.8,
        language_score=0.8,
        cv_language="en",
    )
    repo.create_match(m1)
    repo.create_match(m2)
    latest = repo.get_latest_match(tracked_app.id)
    assert latest is not None
    assert latest.overall_score == 0.8
    assert len(repo.list_matches(tracked_app.id)) == 2


def test_create_and_get_latest_optimization(repo, tracked_app):
    opt = ApplicationCvOptimization(
        application_id=tracked_app.id,
        cv_language="en",
        original_tex="orig",
        optimized_tex="opt",
        improvement_summary="summary",
        changes=[],
    )
    repo.create_optimization(opt)
    latest = repo.get_latest_optimization(tracked_app.id)
    assert latest is not None
    assert latest.optimized_tex == "opt"


def test_create_and_get_latest_interview_prep(repo, tracked_app):
    prep = ApplicationInterviewPrep(
        application_id=tracked_app.id,
        competencies_to_probe=["leadership"],
    )
    repo.create_interview_prep(prep)
    latest = repo.get_latest_interview_prep(tracked_app.id)
    assert latest is not None
    assert latest.competencies_to_probe == ["leadership"]


def test_list_all_cover_letters_paginates_and_counts(repo, tracked_app):
    for i in range(3):
        repo.create_cover_letter(
            ApplicationCoverLetter(
                application_id=tracked_app.id, body=f"body {i}", tone="professional"
            )
        )

    assert repo.count_all_cover_letters() == 3

    first = repo.list_all_cover_letters_with_context(limit=2, offset=0)
    second = repo.list_all_cover_letters_with_context(limit=2, offset=2)
    assert len(first) == 2
    assert len(second) == 1

    # Stable, non-overlapping pages (id tiebreaker on equal created_at).
    ids = {row["id"] for row in first} | {row["id"] for row in second}
    assert len(ids) == 3
