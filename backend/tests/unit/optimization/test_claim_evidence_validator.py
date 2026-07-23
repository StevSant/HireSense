import uuid

from hiresense.claims.domain import CandidateClaim, ClaimVerificationStatus
from hiresense.optimization.domain import ClaimEvidenceValidator
from hiresense.optimization.domain.models import SectionChange


def test_readiness_reports_unsupported_claims_with_rejection_reasons() -> None:
    original_tex = "Built Python APIs that served 5 customers"
    changes = [
        SectionChange(
            section_name="SUMMARY",
            original="Built Python APIs that served 5 customers",
            optimized="Built Python APIs that served 10 Kubernetes customers",
            reason="Match the role",
        )
    ]

    readiness = ClaimEvidenceValidator().evaluate(
        original_tex,
        changes,
        job_skills=["python", "kubernetes"],
    )

    assert not readiness.ready
    assert readiness.supported_changes == []
    assert readiness.blocked_changes[0].reason == "unsupported_job_skill"


def test_readiness_does_not_use_an_unrelated_cv_number_as_evidence() -> None:
    original_tex = "Built Python APIs for 5 customers. Reduced latency by 20%."
    changes = [
        SectionChange(
            section_name="SUMMARY",
            original="Built Python APIs for 5 customers.",
            optimized="Built Python APIs for 20 customers.",
            reason="Strengthen impact",
        )
    ]

    readiness = ClaimEvidenceValidator().evaluate(original_tex, changes, job_skills=["python"])

    assert not readiness.ready
    assert readiness.supported_changes == []
    assert readiness.blocked_changes[0].reason == "unsupported_numeric_claim"


def test_readiness_uses_verified_claim_with_provenance_for_new_skill_and_number() -> None:
    change = SectionChange(
        section_name="SUMMARY",
        original="Built Python APIs.",
        optimized="Built Python APIs and Kubernetes services that reduced latency by 40%.",
        reason="Match the role",
    )
    claim = CandidateClaim(
        id=uuid.uuid4(),
        text="Built Kubernetes services that reduced latency by 40%.",
        source="portfolio",
        provenance="https://example.com/case-study",
        verification_status=ClaimVerificationStatus.VERIFIED,
    )

    readiness = ClaimEvidenceValidator().evaluate(
        "Built Python APIs.",
        [change],
        job_skills=["python", "kubernetes"],
        verified_claims=[claim],
    )

    assert readiness.ready
    assert readiness.supported_changes == [change]
    assert readiness.supported_evidence[0].change == change
    assert readiness.supported_evidence[0].claims[0].provenance == claim.provenance
    assert readiness.supported_evidence[0].claims[0].source == "portfolio"


def test_readiness_never_uses_an_unverified_claim_as_evidence() -> None:
    change = SectionChange(
        section_name="SUMMARY",
        original="Built Python APIs.",
        optimized="Built Python APIs and Kubernetes services.",
        reason="Match the role",
    )
    unverified_claim = CandidateClaim(
        text="Built Kubernetes services.",
        source="notes",
        provenance="Unreviewed note",
    )

    readiness = ClaimEvidenceValidator().evaluate(
        "Built Python APIs.",
        [change],
        job_skills=["python", "kubernetes"],
        verified_claims=[unverified_claim],
    )

    assert not readiness.ready
    assert readiness.blocked_changes[0].reason == "unsupported_job_skill"


def test_readiness_keeps_exact_anchor_requirement_with_verified_evidence() -> None:
    claim = CandidateClaim(
        text="Built Kubernetes services.",
        source="portfolio",
        provenance="https://example.com/case-study",
        verification_status=ClaimVerificationStatus.VERIFIED,
    )
    change = SectionChange(
        section_name="SUMMARY",
        original="Different CV sentence.",
        optimized="Built Kubernetes services.",
        reason="Match the role",
    )

    readiness = ClaimEvidenceValidator().evaluate(
        "Built Python APIs.",
        [change],
        job_skills=["kubernetes"],
        verified_claims=[claim],
    )

    assert not readiness.ready
    assert readiness.blocked_changes[0].reason == "missing_exact_anchor"
