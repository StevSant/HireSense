import pytest

from hiresense.adapters.latex import LatexCompiler
from hiresense.profile.domain.latex_parser import LaTeXParser, ParsedCV, ParsedSection
from hiresense.profile.domain.services import ProfileService
from hiresense.profile.domain.skill_extractor import SkillExtractor


class FakePDFParser:
    """Stands in for pymupdf extraction: returns plain-text ParsedCV content."""

    def __init__(self, parsed: ParsedCV) -> None:
        self._parsed = parsed

    async def parse(self, _file_bytes: bytes) -> ParsedCV:
        return self._parsed


@pytest.mark.asyncio
async def test_pdf_upload_wraps_plaintext_in_compilable_latex(tmp_path) -> None:
    # pymupdf yields plain text with no preamble — the regression that made
    # xelatex fail with "Missing \begin{document}".
    parsed = ParsedCV(
        name="Jane Doe",
        email="jane@example.com",
        phone="+1 555 1234",
        location="New York",
        sections=[ParsedSection(name="SUMMARY", content="Backend engineer.")],
        raw_tex="Jane Doe\nNew York\nSUMMARY\nBackend engineer.",
    )
    service = ProfileService(
        parser=LaTeXParser(),
        skill_extractor=SkillExtractor(),
        pdf_parser=FakePDFParser(parsed),
        latex_compiler=LatexCompiler(),
        cv_directory=str(tmp_path),
    )

    profile = await service.parse_file_and_create(b"%PDF-1.4 fake", "cv.pdf", "en")

    assert "\\documentclass" in profile.raw_tex
    assert "\\begin{document}" in profile.raw_tex
    assert "\\end{document}" in profile.raw_tex
    assert "SUMMARY" in profile.raw_tex


@pytest.mark.asyncio
async def test_pdf_upload_without_compiler_falls_back_to_raw_text(tmp_path) -> None:
    parsed = ParsedCV(name="Jane", sections=[], raw_tex="plain extracted text")
    service = ProfileService(
        parser=LaTeXParser(),
        skill_extractor=SkillExtractor(),
        pdf_parser=FakePDFParser(parsed),
        cv_directory=str(tmp_path),
    )

    profile = await service.parse_file_and_create(b"%PDF-1.4 fake", "cv.pdf", "en")

    assert profile.raw_tex == "plain extracted text"


@pytest.mark.asyncio
async def test_tex_upload_is_stored_verbatim(tmp_path) -> None:
    source = "\\documentclass{article}\n\\begin{document}\nHi\n\\end{document}"
    service = ProfileService(
        parser=LaTeXParser(),
        skill_extractor=SkillExtractor(),
        latex_compiler=LatexCompiler(),
        cv_directory=str(tmp_path),
    )

    profile = await service.parse_file_and_create(source.encode(), "cv.tex", "en")

    assert profile.raw_tex == source
