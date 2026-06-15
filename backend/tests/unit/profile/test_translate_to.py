import pytest

from hiresense.ports import LatexCompileError
from hiresense.profile.domain.latex_parser import LaTeXParser
from hiresense.profile.domain.services import ProfileService
from hiresense.profile.domain.skill_extractor import SkillExtractor

SAMPLE_TEX = r"""
\documentclass{article}
\begin{document}
\begin{center}{\LARGE \textbf{JOHN DOE}}\end{center}
\section*{SUMMARY}
Backend engineer with Python and FastAPI expertise.
\end{document}
"""


class FakeTranslator:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple[str, str, str]] = []

    async def translate(self, raw_tex: str, source_lang: str, target_lang: str) -> str:
        self.calls.append((raw_tex, source_lang, target_lang))
        return self.output


class FakeCompiler:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def compile_to_pdf(self, tex: str) -> bytes:
        if self.fail:
            raise LatexCompileError("boom")
        return b"%PDF-1.4 fake"


def _service(translator: FakeTranslator, compiler: FakeCompiler) -> ProfileService:
    return ProfileService(
        parser=LaTeXParser(),
        skill_extractor=SkillExtractor(),
        translator=translator,
        latex_compiler=compiler,
    )


@pytest.mark.asyncio
async def test_translate_to_creates_flagged_target_variant() -> None:
    translator = FakeTranslator(SAMPLE_TEX)
    service = _service(translator, FakeCompiler())
    await service.parse_and_create(SAMPLE_TEX, language="en")

    outcome = await service.translate_to("es")

    assert outcome.pdf_ok is True
    assert outcome.compile_error is None
    assert outcome.profile.language == "es"
    assert outcome.profile.machine_translated is True
    assert translator.calls == [(SAMPLE_TEX, "en", "es")]


@pytest.mark.asyncio
async def test_translate_to_saves_even_when_compile_fails() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler(fail=True))
    await service.parse_and_create(SAMPLE_TEX, language="en")

    outcome = await service.translate_to("es")

    assert outcome.pdf_ok is False
    assert outcome.compile_error is not None
    assert outcome.profile.machine_translated is True
    saved = await service.get_current_profile(language="es")
    assert saved is not None


@pytest.mark.asyncio
async def test_translate_to_without_source_raises() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler())
    with pytest.raises(ValueError):
        await service.translate_to("es")


@pytest.mark.asyncio
async def test_compile_pdf_returns_bytes() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler())
    await service.parse_and_create(SAMPLE_TEX, language="en")
    pdf = await service.compile_pdf("en")
    assert pdf.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_compile_pdf_missing_language_raises() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler())
    with pytest.raises(ValueError):
        await service.compile_pdf("es")
