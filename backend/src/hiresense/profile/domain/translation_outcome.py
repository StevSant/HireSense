from __future__ import annotations

from dataclasses import dataclass

from hiresense.profile.domain.models import CandidateProfile


@dataclass(frozen=True)
class TranslationOutcome:
    profile: CandidateProfile
    pdf_ok: bool
    compile_error: str | None = None
