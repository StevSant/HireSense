from __future__ import annotations


import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.applications.domain.models import (
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
