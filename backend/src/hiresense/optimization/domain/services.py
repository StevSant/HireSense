from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from hiresense.claims.domain import CandidateClaim, CandidateClaimService
from hiresense.optimization.domain.claim_evidence_validator import ClaimEvidenceValidator
from hiresense.kernel.prompt_boundary import PromptBoundary
from hiresense.optimization.domain.errors import OptimizationError
from hiresense.optimization.domain.models import OptimizationResult, SectionChange
from hiresense.ports.llm import LLMTimeoutError

logger = logging.getLogger(__name__)

_MARKDOWN_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _strip_markdown_fence(text: str) -> str:
    match = _MARKDOWN_FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


class CVOptimizer:
    def __init__(
        self,
        llm: Any,
        job_char_limit: int = 6000,
        claim_service: CandidateClaimService | None = None,
    ) -> None:
        self._llm = llm
        # Caps job_description in the prompt (unbounded free text). Reuses
        # the existing match_deep_job_char_limit value, wired from bootstrap.
        # original_tex is NEVER truncated — _apply_changes() replaces exact
        # substrings against it, so truncating would break that anchor match.
        self._job_char_limit = job_char_limit
        self._claim_evidence_validator = ClaimEvidenceValidator()
        self._claim_service = claim_service

    async def optimize(
        self,
        match_id: str,
        job_id: str,
        cv_id: str,
        original_tex: str,
        job_description: str,
        job_skills: list[str],
        missing_skills: list[str],
        recommendations: list[str],
    ) -> OptimizationResult:
        opt_id = str(uuid.uuid4())
        try:
            verified_claims = self._verified_claims()
            llm_response = await self._get_llm_suggestions(
                original_tex,
                job_description,
                job_skills,
                missing_skills,
                recommendations,
                verified_claims,
            )
            proposed_changes = [SectionChange(**c) for c in llm_response.get("changes", [])]
            claim_readiness = self._claim_evidence_validator.evaluate(
                original_tex,
                proposed_changes,
                job_skills,
                verified_claims=verified_claims,
            )
        except LLMTimeoutError:
            # Let the timeout surface as a 504 (issue #139) rather than folding
            # it into a generic optimization failure.
            raise
        except Exception as exc:
            # Do NOT fall back to returning the original CV byte-for-byte — that
            # persists a fake "success" the user reads as a tailored CV (issue
            # #142). Raise so the API returns a 503.
            logger.exception("CV optimization failed")
            raise OptimizationError("CV optimization failed") from exc

        # A successful call with an empty change list is a legitimate outcome
        # ("no changes suggested"): optimized_tex == original_tex but changes==[]
        # distinguishes it from a failure, which raises above.
        optimized_tex = self._apply_changes(original_tex, claim_readiness.supported_changes)
        return OptimizationResult(
            id=opt_id,
            match_id=match_id,
            job_id=job_id,
            cv_id=cv_id,
            changes=claim_readiness.supported_changes,
            original_tex=original_tex,
            optimized_tex=optimized_tex,
            improvement_summary=llm_response.get("improvement_summary"),
            claim_readiness=claim_readiness,
        )

    def _apply_changes(self, tex: str, changes: list[SectionChange]) -> str:
        result = tex
        for change in changes:
            if change.original in result:
                result = result.replace(change.original, change.optimized, 1)
        return result

    async def _get_llm_suggestions(
        self,
        original_tex: str,
        job_description: str,
        job_skills: list[str],
        missing_skills: list[str],
        recommendations: list[str],
        verified_claims: list[CandidateClaim],
    ) -> dict[str, Any]:
        verified_evidence = self._format_verified_evidence(verified_claims)
        prompt = (
            "You are optimizing a LaTeX CV to better match a specific job.\n\n"
            f"Job Description: {PromptBoundary.untrusted_job_content(job_description, max_chars=self._job_char_limit)}\n"
            f"Required Skills: {', '.join(job_skills)}\n"
            f"Missing Skills: {', '.join(missing_skills)}\n"
            f"Recommendations: {', '.join(recommendations)}\n\n"
            f"Current CV (LaTeX):\n{PromptBoundary.untrusted_cv_content(original_tex)}\n\n"
            f"Verified candidate evidence:\n{verified_evidence}\n\n"
            "Suggest specific text changes to improve the CV's match score.\n"
            "IMPORTANT: Only modify content text, never LaTeX commands or structure.\n"
            "Only describe skills and achievements that are already stated in the Current CV or "
            "the Verified candidate evidence.\n"
            "Verified candidate evidence may support content claims, but every original value must "
            "still be an exact substring from the Current CV.\n"
            "Every original value must be an exact substring from the Current CV.\n"
            "Return a JSON object with:\n"
            '- "changes": list of objects with "section_name", "original" (exact text to replace), '
            '"optimized" (replacement text), "reason"\n'
            '- "improvement_summary": brief summary of changes\n'
            "Return ONLY valid JSON."
        )
        response = await self._llm.complete(
            prompt,
            system=(
                "You are a professional CV optimization assistant. "
                f"{PromptBoundary.untrusted_content_instruction()}"
            ),
        )
        cleaned = _strip_markdown_fence(response)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "CV optimizer got non-JSON LLM response (first 500 chars): %r",
                cleaned[:500],
            )
            raise

    def _verified_claims(self) -> list[CandidateClaim]:
        if self._claim_service is None:
            return []
        return self._claim_service.list_verified_for_readiness()

    @staticmethod
    def _format_verified_evidence(claims: list[CandidateClaim]) -> str:
        if not claims:
            return "None available."
        evidence = "\n".join(
            f"- {claim.text}\n  Source: {claim.source}\n  Provenance: {claim.provenance}"
            for claim in claims
        )
        return PromptBoundary.trusted_candidate_facts(evidence, max_chars=6000)
