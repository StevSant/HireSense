from __future__ import annotations

import enum
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from hiresense.applications.ports import ApplicationRepositoryPort


class ApplicationPacketState(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REVOKED = "revoked"


class ApplicationPacketNotReadyError(ValueError):
    """Raised when a generated application has not passed human review."""


class ApplicationQualityReport(BaseModel):
    ready: bool = False
    checks: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    skill_coverage_ratio: float = 0.0
    checked_at: datetime | None = None


class ApplicationPacket(BaseModel):
    """Immutable snapshot of the inputs and outputs used for an application."""

    id: uuid.UUID | None = None
    application_id: uuid.UUID
    job_snapshot_hash: str
    profile_hash: str
    match_id: uuid.UUID | None = None
    optimization_id: uuid.UUID | None = None
    cover_letter_id: uuid.UUID | None = None
    verified_claim_ids: list[uuid.UUID] = Field(default_factory=list)
    cv_content_hash: str | None = None
    cover_letter_content_hash: str | None = None
    quality_report: ApplicationQualityReport
    state: ApplicationPacketState = ApplicationPacketState.DRAFT
    approved_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


def content_hash(value: object) -> str:
    """Return a stable hash for a JSON-compatible snapshot or text value."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def evaluate_application_quality(
    *,
    required_skills: list[str],
    optimized_cv: str | None,
    cover_letter: str | None,
) -> ApplicationQualityReport:
    """Run deterministic pre-approval checks over generated text artifacts."""
    cv_present = bool((optimized_cv or "").strip())
    letter_present = bool((cover_letter or "").strip())
    combined = f"{optimized_cv or ''}\n{cover_letter or ''}".casefold()
    skills = [skill.strip() for skill in required_skills if skill.strip()]
    covered = sum(1 for skill in skills if skill.casefold() in combined)
    ratio = covered / len(skills) if skills else 1.0
    skill_check = ratio >= 0.5 if skills else True
    warnings: list[str] = []
    if not cv_present:
        warnings.append("A tailored CV is required before approval.")
    if not letter_present:
        warnings.append("A cover letter is required before approval.")
    if skills and not skill_check:
        warnings.append("The generated documents cover fewer than half of the required skills.")
    checks = {
        "cv_present": cv_present,
        "cover_letter_present": letter_present,
        "required_skills_covered": skill_check,
    }
    return ApplicationQualityReport(
        ready=all(checks.values()),
        checks=checks,
        warnings=warnings,
        skill_coverage_ratio=round(ratio, 4),
        checked_at=datetime.now(timezone.utc),
    )


def _profile_snapshot(profile: object | None) -> object:
    if profile is None:
        return {}
    model_dump = getattr(profile, "model_dump", None)
    if model_dump is not None:
        return model_dump(mode="json")
    return {key: value for key, value in vars(profile).items() if not key.startswith("_")}


class ApplicationPacketService:
    def __init__(
        self,
        repository: "ApplicationRepositoryPort",
        tracking_service: Any,
        profile_service: Any,
        claim_service: Any | None = None,
    ) -> None:
        self._repo = repository
        self._tracking = tracking_service
        self._profiles = profile_service
        self._claims = claim_service

    def _build(self, application_id: uuid.UUID) -> ApplicationPacket:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")
        self._tracking.get(application_id)
        match = self._repo.get_latest_match(application_id)
        optimization = self._repo.get_latest_optimization(application_id)
        letter = self._repo.get_latest_cover_letter(application_id)
        language = optimization.cv_language if optimization is not None else "en"
        profile = self._profiles.get_for_language(language)
        claims = self._claims.list_verified_for_readiness() if self._claims is not None else []
        quality = evaluate_application_quality(
            required_skills=list(snapshot.required_skills or []),
            optimized_cv=optimization.optimized_tex if optimization is not None else None,
            cover_letter=letter.body if letter is not None else None,
        )
        packet = ApplicationPacket(
            application_id=application_id,
            job_snapshot_hash=content_hash(
                {
                    "description": snapshot.description,
                    "required_skills": list(snapshot.required_skills or []),
                    "source": snapshot.source,
                }
            ),
            profile_hash=content_hash(_profile_snapshot(profile)),
            match_id=match.id if match is not None else None,
            optimization_id=optimization.id if optimization is not None else None,
            cover_letter_id=letter.id if letter is not None else None,
            verified_claim_ids=[claim.id for claim in claims if claim.id is not None],
            cv_content_hash=(content_hash(optimization.optimized_tex) if optimization else None),
            cover_letter_content_hash=(content_hash(letter.body) if letter else None),
            quality_report=quality,
        )
        return packet

    def create(self, application_id: uuid.UUID) -> ApplicationPacket:
        return self._repo.create_packet(self._build(application_id))

    def latest(self, application_id: uuid.UUID) -> ApplicationPacket | None:
        return self._repo.get_latest_packet(application_id)

    def is_current(self, packet: ApplicationPacket) -> bool:
        """Check that an approved packet still describes today's artifacts."""
        current = self._build(packet.application_id)
        return all(
            getattr(packet, field) == getattr(current, field)
            for field in (
                "job_snapshot_hash",
                "profile_hash",
                "match_id",
                "optimization_id",
                "cover_letter_id",
                "verified_claim_ids",
                "cv_content_hash",
                "cover_letter_content_hash",
            )
        )

    def approve(self, packet_id: uuid.UUID) -> ApplicationPacket:
        packet = self._repo.get_packet(packet_id)
        if packet is None:
            raise ValueError(f"Application packet {packet_id} not found")
        if packet.state is ApplicationPacketState.REVOKED:
            raise ApplicationPacketNotReadyError("A revoked application packet cannot be approved")
        if not packet.quality_report.ready:
            raise ApplicationPacketNotReadyError("Application packet is not ready for approval")
        return self._repo.set_packet_state(packet_id, ApplicationPacketState.APPROVED)

    def revoke(self, packet_id: uuid.UUID) -> ApplicationPacket:
        packet = self._repo.get_packet(packet_id)
        if packet is None:
            raise ValueError(f"Application packet {packet_id} not found")
        return self._repo.set_packet_state(packet_id, ApplicationPacketState.REVOKED)

    def export_packet(self, application_id: uuid.UUID) -> dict[str, Any]:
        packet = self.latest(application_id)
        if packet is None:
            raise ValueError(f"No application packet exists for {application_id}")
        return packet.model_dump(mode="json")

    def restore_packet(
        self, application_id: uuid.UUID, payload: dict[str, Any]
    ) -> ApplicationPacket:
        """Restore a validated export as a new, unapproved snapshot.

        Imported approval timestamps and IDs are deliberately discarded. A
        restore is evidence for review, never proof of current approval.
        """
        imported = ApplicationPacket.model_validate(payload)
        if imported.application_id != application_id:
            raise ValueError("Export belongs to a different application")
        current = self.create(application_id)
        if (
            imported.job_snapshot_hash != current.job_snapshot_hash
            or imported.profile_hash != current.profile_hash
            or imported.match_id != current.match_id
            or imported.optimization_id != current.optimization_id
            or imported.cover_letter_id != current.cover_letter_id
        ):
            raise ValueError("Export no longer matches the current application artifacts")
        # Recompute quality and claim references from current state. Imported
        # approval state and report data are never trusted during restore.
        return current
