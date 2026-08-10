from __future__ import annotations

from typing import Protocol


class LatexCompileError(RuntimeError):
    """Raised when the LaTeX compiler fails to produce a PDF."""


class LatexCompilerPort(Protocol):
    """Renders and compiles LaTeX for application artifacts (CV, cover letter)."""

    async def compile_to_pdf(self, tex_source: str) -> bytes: ...

    def render_cover_letter_tex(
        self,
        *,
        body: str,
        candidate_name: str,
        candidate_email: str | None,
        candidate_phone: str | None,
        company: str,
        date_str: str,
    ) -> str: ...

    def render_cv_tex(
        self,
        *,
        name: str,
        email: str | None,
        phone: str | None,
        location: str | None,
        sections: list[tuple[str, str]],
    ) -> str: ...
