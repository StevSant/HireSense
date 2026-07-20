from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime
from typing import Any

import logging

from hiresense.ports import LatexCompileError, LatexCompilerPort
from hiresense.kernel.exceptions import NotFoundError
from hiresense.applications.domain.aggregate import CoverLetterView
from hiresense.applications.domain.ats_field_map import build_autofill_plan
from hiresense.applications.domain.autofill_plan_view import AutofillPlanView
from hiresense.applications.domain.cover_letter_generator import CoverLetterGenerator
from hiresense.applications.domain.models import ApplicationCoverLetter
from hiresense.applications.ports import ApplicationRepositoryPort
from hiresense.ingestion.domain import classify_application
from hiresense.profile.domain import build_prefill
from hiresense.tracking.domain.models import ApplicationStatus

logger = logging.getLogger(__name__)

# Cover letters are rendered in English for now; contact details are read from
# the candidate's English profile variant.
COVER_LETTER_LANGUAGE = "en"
# Letterhead fallback so the LaTeX still compiles before any profile is uploaded.
PLACEHOLDER_CANDIDATE_NAME = "Candidate"


class ApplyService:
    def __init__(
        self,
        repository: ApplicationRepositoryPort,
        cover_letter_generator: CoverLetterGenerator,
        latex_compiler: LatexCompilerPort,
        profile_service: Any,
        tracking_service: Any,
        *,
        portfolio_citation: Any = None,
    ) -> None:
        self._repo = repository
        self._generator = cover_letter_generator
        self._latex = latex_compiler
        self._profiles = profile_service
        self._tracking = tracking_service
        self._portfolio_citation = portfolio_citation

    async def generate_cover_letter(
        self,
        application_id: uuid.UUID,
        cv_language: str = "en",
        tone: str = "professional",
    ) -> CoverLetterView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise NotFoundError(f"Snapshot for {application_id} not found")
        tracked = self._tracking.get(application_id)
        profile = self._profiles.get_for_language(cv_language)
        if profile is None:
            raise NotFoundError(f"Profile for language '{cv_language}' not found")

        latest_match = self._repo.get_latest_match(application_id)
        pros = list(latest_match.pros) if latest_match else []
        missing = list(latest_match.missing_skills) if latest_match else []
        match_id = latest_match.id if latest_match else None

        portfolio_section = None
        if self._portfolio_citation is not None:
            portfolio_section = await self._portfolio_citation.citation_for(
                job_skills=list(snapshot.required_skills or []),
                job_text=snapshot.description or "",
                application_id=str(application_id),
                language=cv_language,
            )

        body = await self._generator.generate(
            title=tracked.title,
            company=tracked.company,
            description=snapshot.description,
            candidate_summary=getattr(profile, "summary", "") or "",
            candidate_skills=list(getattr(profile, "skills", []) or []),
            required_skills=list(snapshot.required_skills or []),
            pros=pros,
            missing_skills=missing,
            tone=tone,
            portfolio_section=portfolio_section,
        )

        row = ApplicationCoverLetter(
            application_id=application_id,
            match_id=match_id,
            body=body,
            tone=tone,
        )
        saved = self._repo.create_cover_letter(row)
        return CoverLetterView(
            id=saved.id,
            match_id=saved.match_id,
            body=saved.body,
            tone=saved.tone,
            created_at=saved.created_at,
        )

    async def compile_cv_pdf(
        self,
        application_id: uuid.UUID,
        optimization_id: uuid.UUID | None = None,
        *,
        original: bool = False,
        language: str = "en",
    ) -> bytes:
        """Compile the application CV to PDF.

        Defaults to the latest optimization (or `optimization_id` if given).
        Pass `original=True` to compile the user's untouched profile CV in
        the requested language — useful before an optimization has been run.
        """
        if original:
            profile_view = self._profiles.get_for_language(language)
            if profile_view is None or not profile_view.raw_tex:
                raise ValueError(
                    f"No profile CV found for language '{language}' — upload one first"
                )
            return await self._latex.compile_to_pdf(profile_view.raw_tex)

        if optimization_id is None:
            opt = self._repo.get_latest_optimization(application_id)
        else:
            opt = self._repo.get_optimization(optimization_id)
        if opt is None:
            raise ValueError("No CV optimization found — run optimize first")
        try:
            return await self._latex.compile_to_pdf(opt.optimized_tex)
        except LatexCompileError:
            logger.warning(
                "Optimized TeX failed to compile for application %s — falling back to original_tex",
                application_id,
            )
            return await self._latex.compile_to_pdf(opt.original_tex)

    async def compile_cover_letter_pdf(
        self,
        application_id: uuid.UUID,
        cover_letter_id: uuid.UUID | None = None,
    ) -> bytes:
        if cover_letter_id is None:
            letter = self._repo.get_latest_cover_letter(application_id)
        else:
            letter = self._repo.get_cover_letter(cover_letter_id)
        if letter is None:
            raise ValueError("No cover letter found — generate one first")
        tracked = self._tracking.get(application_id)

        # Letterhead contact details come from the candidate's English profile
        # via the profile service's public port. Fall back to a placeholder name
        # so the LaTeX still compiles when no profile exists yet.
        contact = self._profiles.get_contact_info(COVER_LETTER_LANGUAGE)

        tex_source = self._latex.render_cover_letter_tex(
            body=letter.body,
            candidate_name=(
                contact.name if contact and contact.name else PLACEHOLDER_CANDIDATE_NAME
            ),
            candidate_email=contact.email if contact else None,
            candidate_phone=contact.phone if contact else None,
            company=tracked.company,
            date_str=datetime.now().strftime("%B %d, %Y"),
        )
        return await self._latex.compile_to_pdf(tex_source)

    async def build_bundle(
        self,
        application_id: uuid.UUID,
    ) -> bytes:
        cv_pdf = await self.compile_cv_pdf(application_id)
        letter_pdf = await self.compile_cover_letter_pdf(application_id)
        tracked = self._tracking.get(application_id)
        safe_company = "".join(c if c.isalnum() else "_" for c in tracked.company)[:40] or "company"

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"cv_{safe_company}.pdf", cv_pdf)
            zf.writestr(f"cover_letter_{safe_company}.pdf", letter_pdf)
        return buf.getvalue()

    async def autofill_plan(self, application_id: uuid.UUID) -> AutofillPlanView:
        """One-call Apply Assist handoff: classify how to apply to this
        application's job and produce the per-field autofill plan from the
        candidate's profile. Raises ValueError if the application is missing.
        """
        tracked = self._tracking.get(application_id)  # ValueError if missing
        classification = classify_application(getattr(tracked, "url", None))
        profile = await self._profiles.get_current_profile()
        prefill = build_prefill(profile) if profile is not None else {}
        return AutofillPlanView(
            application_method=classification.application_method.value,
            ats_type=classification.ats_type,
            apply_url=classification.apply_url,
            fills=build_autofill_plan(classification.ats_type, prefill),
        )

    async def mark_applied(self, application_id: uuid.UUID) -> None:
        # Idempotent: set status=APPLIED, set applied_at if not already set.
        await self._tracking.update_status(
            application_id,
            ApplicationStatus.APPLIED,
        )
