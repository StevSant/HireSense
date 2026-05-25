from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

import logging

from hiresense.adapters.latex import LatexCompileError, LatexCompiler
from hiresense.applications.domain.aggregate import CoverLetterView
from hiresense.applications.domain.cover_letter_generator import CoverLetterGenerator
from hiresense.applications.domain.models import ApplicationCoverLetter
from hiresense.applications.ports import ApplicationRepositoryPort
from hiresense.tracking.domain.models import ApplicationStatus

logger = logging.getLogger(__name__)


class ApplyService:
    def __init__(
        self,
        repository: ApplicationRepositoryPort,
        cover_letter_generator: CoverLetterGenerator,
        latex_compiler: LatexCompiler,
        profile_service: Any,
        tracking_service: Any,
    ) -> None:
        self._repo = repository
        self._generator = cover_letter_generator
        self._latex = latex_compiler
        self._profiles = profile_service
        self._tracking = tracking_service

    async def generate_cover_letter(
        self,
        application_id: uuid.UUID,
        cv_language: str = "en",
        tone: str = "professional",
    ) -> CoverLetterView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")
        tracked = self._tracking.get(application_id)
        profile = self._profiles.get_for_language(cv_language)
        if profile is None:
            raise ValueError(f"Profile for language '{cv_language}' not found")

        latest_match = self._repo.get_latest_match(application_id)
        pros = list(latest_match.pros) if latest_match else []
        missing = list(latest_match.missing_skills) if latest_match else []
        match_id = latest_match.id if latest_match else None

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
    ) -> bytes:
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
        profile = self._profiles.get_for_language("en")  # cover letter is always English for now

        candidate_name = getattr(profile, "language", None) and "Bryan Menoscal" or "Candidate"
        # Pull name/contact from the underlying CandidateProfile via the latest profile lookup.
        candidate_info = self._candidate_info(profile)

        tex_source = self._latex.render_cover_letter_tex(
            body=letter.body,
            candidate_name=candidate_info["name"],
            candidate_email=candidate_info["email"],
            candidate_phone=candidate_info["phone"],
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

    def mark_applied(self, application_id: uuid.UUID) -> None:
        # Idempotent: set status=APPLIED, set applied_at if not already set.
        self._tracking.update_status(
            application_id,
            ApplicationStatus.APPLIED,
        )

    # ---- internal ----------------------------------------------------

    def _candidate_info(self, profile: Any) -> dict[str, str | None]:
        # ProfileLanguageView doesn't carry name/email/phone; pull from the
        # underlying repo through profile_service if exposed. Fall back to
        # placeholders so the LaTeX still compiles.
        name = "Candidate"
        email: str | None = None
        phone: str | None = None
        latest = getattr(self._profiles, "_get_latest_for_language_sync", None)
        if latest is not None and profile is not None:
            full = latest(profile.language)
            if full is not None:
                name = full.name or name
                email = full.email
                phone = full.phone
        return {"name": name, "email": email, "phone": phone}
