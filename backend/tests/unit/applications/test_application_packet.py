from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from hiresense.applications.domain.application_packet import (
    ApplicationPacket,
    ApplicationQualityReport,
    ApplicationPacketService,
    content_hash,
    evaluate_application_quality,
)


def test_quality_report_requires_both_artifacts_and_skill_coverage() -> None:
    report = evaluate_application_quality(
        required_skills=["Python", "PostgreSQL"],
        optimized_cv="Built Python services",
        cover_letter="I enjoy working with PostgreSQL.",
    )

    assert report.ready is True
    assert report.skill_coverage_ratio == 1.0
    assert report.checks == {
        "cv_present": True,
        "cover_letter_present": True,
        "required_skills_covered": True,
    }


def test_quality_report_explains_missing_artifacts() -> None:
    report = evaluate_application_quality(
        required_skills=["Python", "PostgreSQL", "Docker"],
        optimized_cv="Built Python services",
        cover_letter=None,
    )

    assert report.ready is False
    assert report.checks["cover_letter_present"] is False
    assert any("cover letter" in warning.lower() for warning in report.warnings)


def test_content_hash_is_stable_for_mapping_order() -> None:
    assert content_hash({"b": 2, "a": 1}) == content_hash({"a": 1, "b": 2})


class _Repo:
    def __init__(self, packet=None):
        self.packet = packet
        self.saved_state = None

    def get_packet(self, packet_id):
        return self.packet

    def set_packet_state(self, packet_id, state):
        self.saved_state = state
        return self.packet.model_copy(update={"state": state})


def test_approval_rejects_packet_that_is_not_ready() -> None:
    packet_id = uuid.uuid4()
    packet = ApplicationPacket(
        id=packet_id,
        application_id=uuid.uuid4(),
        job_snapshot_hash="a" * 64,
        profile_hash="b" * 64,
        quality_report=ApplicationQualityReport(ready=False),
    )
    service = ApplicationPacketService(_Repo(packet), object(), object())

    with pytest.raises(ValueError, match="not ready"):
        service.approve(packet_id)


def test_create_packet_records_current_artifact_and_claim_versions() -> None:
    application_id = uuid.uuid4()
    match_id = uuid.uuid4()
    optimization_id = uuid.uuid4()
    letter_id = uuid.uuid4()

    class Repo:
        def __init__(self):
            self.created = None

        def get_snapshot(self, _id):
            return SimpleNamespace(description="Build Python APIs", required_skills=["Python"], source="ingested")

        def get_latest_match(self, _id):
            return SimpleNamespace(id=match_id)

        def get_latest_optimization(self, _id):
            return SimpleNamespace(id=optimization_id, cv_language="en", optimized_tex="Python CV")

        def get_latest_cover_letter(self, _id):
            return SimpleNamespace(id=letter_id, body="I build Python APIs.")

        def create_packet(self, packet):
            self.created = packet
            return packet.model_copy(update={"id": uuid.uuid4()})

    class Claims:
        def list_verified_for_readiness(self):
            return [SimpleNamespace(id=uuid.uuid4())]

    repo = Repo()
    service = ApplicationPacketService(
        repo,
        SimpleNamespace(get=lambda _id: object()),
        SimpleNamespace(get_for_language=lambda _language: SimpleNamespace(model_dump=lambda mode: {"skills": ["Python"]})),
        Claims(),
    )

    packet = service.create(application_id)
    assert packet.id is not None
    assert packet.application_id == application_id
    assert packet.match_id == match_id
    assert packet.optimization_id == optimization_id
    assert packet.cover_letter_id == letter_id
    assert packet.quality_report.ready is True
    assert packet.verified_claim_ids
