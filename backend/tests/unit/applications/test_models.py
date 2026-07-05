from __future__ import annotations

import uuid

from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
    JobSnapshotSource,
)


def test_job_snapshot_defaults_and_required_fields() -> None:
    snap = ApplicationJobSnapshot(
        application_id=uuid.uuid4(),
        description="some description",
        required_skills=["python", "fastapi"],
        source=JobSnapshotSource.MANUAL.value,
    )
    assert snap.description == "some description"
    assert snap.required_skills == ["python", "fastapi"]
    assert snap.source == "manual"


def test_application_match_all_score_fields() -> None:
    match = ApplicationMatch(
        application_id=uuid.uuid4(),
        overall_score=0.82,
        semantic_score=0.7,
        skill_score=0.9,
        experience_score=0.8,
        language_score=0.85,
        matched_skills=["python"],
        missing_skills=["k8s"],
        pros=["good fit"],
        cons=["missing k8s"],
        recommendations=["learn k8s"],
        cv_language="en",
    )
    assert match.overall_score == 0.82
    assert "python" in match.matched_skills


def test_application_cv_optimization_links_to_match() -> None:
    opt = ApplicationCvOptimization(
        application_id=uuid.uuid4(),
        match_id=uuid.uuid4(),
        cv_language="en",
        original_tex=r"\documentclass{article}",
        optimized_tex=r"\documentclass{article}\begin{document}\end{document}",
        improvement_summary="tightened skills section",
        changes=[{"section": "skills", "before": "", "after": "python, k8s"}],
    )
    assert opt.cv_language == "en"
    assert opt.match_id is not None


def test_application_interview_prep_lists() -> None:
    prep = ApplicationInterviewPrep(
        application_id=uuid.uuid4(),
        competencies_to_probe=["leadership"],
        technical_topics=["distributed systems"],
        negotiation_points=["remote-first"],
        matched_stories=[
            {"story_id": str(uuid.uuid4()), "story_title": "led migration", "relevance": "high"}
        ],
    )
    assert prep.competencies_to_probe == ["leadership"]
