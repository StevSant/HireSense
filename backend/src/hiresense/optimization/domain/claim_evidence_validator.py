from __future__ import annotations

import re

from hiresense.claims.domain import CandidateClaim, ClaimVerificationStatus
from hiresense.kernel import normalize_skill
from hiresense.optimization.domain.models import (
    BlockedClaim,
    ClaimBlockerReason,
    ClaimReadiness,
    SectionChange,
    SupportedChangeEvidence,
    VerifiedClaimEvidence,
)


class ClaimEvidenceValidator:
    """Keeps generated CV edits tied to text already present in the CV."""

    def supported_changes(
        self,
        original_tex: str,
        proposed_changes: list[SectionChange],
        job_skills: list[str],
        verified_claims: list[CandidateClaim] | None = None,
    ) -> list[SectionChange]:
        return self.evaluate(
            original_tex,
            proposed_changes,
            job_skills,
            verified_claims=verified_claims,
        ).supported_changes

    def evaluate(
        self,
        original_tex: str,
        proposed_changes: list[SectionChange],
        job_skills: list[str],
        verified_claims: list[CandidateClaim] | None = None,
    ) -> ClaimReadiness:
        canonical_job_skills = {
            canonical for skill in job_skills if (canonical := normalize_skill(skill))
        }
        approved_claims = [
            claim
            for claim in verified_claims or []
            if claim.verification_status is ClaimVerificationStatus.VERIFIED
        ]
        supported_changes: list[SectionChange] = []
        blocked_changes: list[BlockedClaim] = []
        supported_evidence: list[SupportedChangeEvidence] = []
        for change in proposed_changes:
            blocker, evidence = self._evaluate_change(
                change,
                original_tex,
                canonical_job_skills,
                approved_claims,
            )
            if blocker is None:
                supported_changes.append(change)
                if evidence:
                    supported_evidence.append(
                        SupportedChangeEvidence(change=change, claims=evidence)
                    )
            else:
                blocked_changes.append(BlockedClaim(change=change, reason=blocker))
        return ClaimReadiness(
            ready=not blocked_changes,
            supported_changes=supported_changes,
            blocked_changes=blocked_changes,
            supported_evidence=supported_evidence,
        )

    def _evaluate_change(
        self,
        change: SectionChange,
        original_tex: str,
        job_skills: set[str],
        verified_claims: list[CandidateClaim],
    ) -> tuple[ClaimBlockerReason | None, list[VerifiedClaimEvidence]]:
        if not self._has_exact_anchor(change, original_tex):
            return "missing_exact_anchor", []

        evidence: list[VerifiedClaimEvidence] = []
        for skill in self._new_job_skills(change, original_tex, job_skills):
            claim = self._first_claim_supporting(skill, verified_claims)
            if claim is None:
                return "unsupported_job_skill", []
            evidence.append(self._as_evidence(claim))

        for number in self._new_numbers(change):
            claim = self._first_claim_supporting(number, verified_claims)
            if claim is None:
                return "unsupported_numeric_claim", []
            evidence.append(self._as_evidence(claim))
        return None, self._unique_evidence(evidence)

    @staticmethod
    def _has_exact_anchor(change: SectionChange, original_tex: str) -> bool:
        return bool(change.original.strip()) and change.original in original_tex

    def _new_job_skills(
        self,
        change: SectionChange,
        original_tex: str,
        job_skills: set[str],
    ) -> list[str]:
        return [
            skill
            for skill in job_skills
            if self._contains_skill(change.optimized, skill)
            and not self._contains_skill(original_tex, skill)
        ]

    @staticmethod
    def _contains_skill(text: str, skill: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", text, re.IGNORECASE) is not None

    @staticmethod
    def _new_numbers(change: SectionChange) -> set[str]:
        original_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", change.original))
        replacement_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", change.optimized))
        return replacement_numbers - original_numbers

    def _first_claim_supporting(
        self, value: str, verified_claims: list[CandidateClaim]
    ) -> CandidateClaim | None:
        return next(
            (claim for claim in verified_claims if self._contains_skill(claim.text, value)),
            None,
        )

    @staticmethod
    def _as_evidence(claim: CandidateClaim) -> VerifiedClaimEvidence:
        return VerifiedClaimEvidence(
            claim_id=claim.id,
            text=claim.text,
            source=claim.source,
            provenance=claim.provenance,
        )

    @staticmethod
    def _unique_evidence(
        evidence: list[VerifiedClaimEvidence],
    ) -> list[VerifiedClaimEvidence]:
        unique: dict[tuple[object, str, str, str], VerifiedClaimEvidence] = {}
        for item in evidence:
            unique[(item.claim_id, item.text, item.source, item.provenance)] = item
        return list(unique.values())
