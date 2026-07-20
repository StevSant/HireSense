import logging
import shutil
import subprocess
from pathlib import Path

import pytest

from hiresense.adapters.latex import LatexCompiler
from hiresense.ports import LatexCompileError


def _render(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "name": "Jane Doe",
        "email": None,
        "phone": None,
        "location": None,
        "sections": [],
    }
    kwargs.update(overrides)
    return LatexCompiler().render_cv_tex(**kwargs)  # type: ignore[arg-type]


def test_render_cv_tex_produces_compilable_skeleton() -> None:
    tex = _render(
        email="jane@example.com",
        phone="+1 555 1234",
        location="New York, USA",
        sections=[("SUMMARY", "Backend engineer with Python expertise.")],
    )
    assert "\\documentclass" in tex
    assert "\\begin{document}" in tex
    assert tex.rstrip().endswith("\\end{document}")
    assert "Jane Doe" in tex
    assert "SUMMARY" in tex
    assert "Backend engineer" in tex


def test_render_cv_tex_escapes_special_characters() -> None:
    # Arbitrary extracted text must never break compilation.
    tex = _render(sections=[("R&D", "100% coverage of C# and legacy_code")])
    assert "\\&" in tex
    assert "\\%" in tex
    assert "\\#" in tex
    assert "\\_" in tex


def test_render_cv_tex_renders_bullet_paragraph_as_itemize() -> None:
    tex = _render(sections=[("EXPERIENCE", "- built X\n- shipped Y")])
    assert "\\begin{itemize}" in tex
    assert "\\item built X" in tex
    assert "\\item shipped Y" in tex


def test_render_cv_tex_omits_empty_sections() -> None:
    tex = _render(sections=[("EMPTY", "   "), ("REAL", "content here")])
    assert "EMPTY" not in tex
    assert "REAL" in tex


@pytest.mark.asyncio
async def test_compile_failure_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    compiler = LatexCompiler()

    def _boom(_tex: str) -> bytes:
        raise LatexCompileError("xelatex exited with code 1\nMissing \\begin{document}.")

    monkeypatch.setattr(compiler, "_compile_sync", _boom)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LatexCompileError):
            await compiler.compile_to_pdf("plain text, not latex")

    assert any("LaTeX compilation failed" in record.message for record in caplog.records)


def test_run_once_disables_shell_escape_and_file_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Untrusted LaTeX (raw user CVs and LLM-spliced optimized CVs) both flow
    # through this single argv, so asserting the flags here covers both paths.
    captured: dict[str, object] = {}

    def _fake_run(argv: list[str], **kwargs: object):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    compiler = LatexCompiler()
    compiler._run_once(Path("/tmp/work"), Path("/tmp/work/doc.tex"))

    argv = captured["argv"]
    assert "-no-shell-escape" in argv  # type: ignore[operator]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["openin_any"] == "p"
    assert env["openout_any"] == "p"


@pytest.mark.parametrize(
    "malicious",
    [
        r"\documentclass{article}\begin{document}\write18{echo pwned}\end{document}",
        r"\documentclass{article}\begin{document}\input{/etc/passwd}\end{document}",
    ],
)
@pytest.mark.skipif(shutil.which("xelatex") is None, reason="xelatex not installed")
@pytest.mark.asyncio
async def test_real_compile_rejects_shell_escape_and_abs_input(malicious: str) -> None:
    # Real-compile guard: with -no-shell-escape and openin_any=p, \write18 and
    # absolute \input must fail the compile rather than execute / read the file.
    with pytest.raises(LatexCompileError):
        await LatexCompiler().compile_to_pdf(malicious)
