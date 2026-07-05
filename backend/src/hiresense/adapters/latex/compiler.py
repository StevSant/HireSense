from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import textwrap
from pathlib import Path

from opentelemetry import trace

from hiresense.observability import get_tracer
from hiresense.ports.latex_compiler_port import LatexCompileError

logger = logging.getLogger(__name__)

_tracer = get_tracer("hiresense.latex")


class LatexCompiler:
    """Compiles LaTeX source to PDF via the xelatex binary.

    The compiler shells out to `xelatex -interaction=nonstopmode -halt-on-error`
    in a temp directory and returns the PDF bytes. Two passes are run so refs
    resolve. The temp directory is cleaned up automatically.
    """

    def __init__(self, compiler: str = "xelatex", timeout_seconds: float = 60.0) -> None:
        self._compiler = compiler
        self._timeout = timeout_seconds

    async def compile_to_pdf(self, tex_source: str) -> bytes:
        loop = asyncio.get_running_loop()
        # Wrap every compile in a span + log so failures are never swallowed
        # silently. Callers that handle LatexCompileError (e.g. the translation
        # sanity-check, or the optimized→original CV fallback) still surface the
        # failure in traces/logs even though the request itself succeeds.
        with _tracer.start_as_current_span("latex.compile") as span:
            try:
                return await loop.run_in_executor(None, self._compile_sync, tex_source)
            except LatexCompileError as exc:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                span.record_exception(exc)
                logger.warning("LaTeX compilation failed: %s", exc)
                raise

    def _compile_sync(self, tex_source: str) -> bytes:
        # Sanitize the source:
        # 1. Round-trip through UTF-8 with errors="replace" to drop lone
        #    surrogates and other non-UTF-8 contamination from upstream encoders.
        # 2. Normalize line endings to plain LF. Path.write_text on Windows
        #    defaults to newline=None which translates \n → \r\n, so any
        #    existing \r in the source becomes \r\r\n on disk — which breaks
        #    LaTeX argument parsing for commands like \titleformat.
        cleaned = tex_source.encode("utf-8", errors="replace").decode("utf-8")
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        with tempfile.TemporaryDirectory(prefix="hiresense-tex-") as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "doc.tex"
            # newline="" disables Python's universal-newlines translation on
            # write so our normalized LFs land on disk unchanged.
            source_path.write_text(cleaned, encoding="utf-8", newline="")

            for _ in range(2):
                result = self._run_once(tmp_path, source_path)
                if result.returncode != 0:
                    log = self._tail_log(tmp_path / "doc.log")
                    raise LatexCompileError(
                        f"{self._compiler} exited with code {result.returncode}.\n"
                        f"Last log lines:\n{log}"
                    )

            pdf_path = tmp_path / "doc.pdf"
            if not pdf_path.exists():
                raise LatexCompileError(f"{self._compiler} produced no PDF")
            return pdf_path.read_bytes()

    def _run_once(self, working_dir: Path, source: Path):
        import subprocess

        return subprocess.run(
            [
                self._compiler,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                str(working_dir),
                str(source),
            ],
            cwd=working_dir,
            capture_output=True,
            timeout=self._timeout,
        )

    @staticmethod
    def _tail_log(log_path: Path, lines: int = 40) -> str:
        if not log_path.exists():
            return "(no log)"
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "(log read failed)"
        return "\n".join(text.splitlines()[-lines:])

    def render_cover_letter_tex(
        self,
        *,
        body: str,
        candidate_name: str,
        candidate_email: str | None,
        candidate_phone: str | None,
        company: str,
        date_str: str,
    ) -> str:
        """Wraps a plain-text cover letter body in a minimal LaTeX template."""
        contact_lines = []
        if candidate_email:
            contact_lines.append(_latex_escape(candidate_email))
        if candidate_phone:
            contact_lines.append(_latex_escape(candidate_phone))
        contact = " \\textbullet{} ".join(contact_lines)

        escaped_body = _latex_escape(body).replace("\n\n", "\n\n\\par\n\n")
        return textwrap.dedent(rf"""
        \documentclass[11pt]{{letter}}
        \usepackage[a4paper, margin=1in]{{geometry}}
        \usepackage{{parskip}}
        \usepackage{{hyperref}}
        \pagestyle{{empty}}
        \begin{{document}}
        \begin{{flushleft}}
        \textbf{{{_latex_escape(candidate_name)}}}\\
        {contact}
        \end{{flushleft}}

        \bigskip
        {_latex_escape(date_str)}

        \bigskip
        Hiring Team\\
        {_latex_escape(company)}

        \bigskip
        Dear Hiring Team,

        \medskip
        {escaped_body}

        \bigskip
        Sincerely,\\
        {_latex_escape(candidate_name)}
        \end{{document}}
        """).strip()

    def render_cv_tex(
        self,
        *,
        name: str,
        email: str | None,
        phone: str | None,
        location: str | None,
        sections: list[tuple[str, str]],
    ) -> str:
        """Wrap structured, plain-text CV content in a compilable LaTeX template.

        Used for CVs ingested from non-LaTeX sources (e.g. PDF uploads): the
        extracted text has no preamble, so feeding it straight to xelatex fails
        with "Missing \\begin{document}". Every heading/body is LaTeX-escaped so
        arbitrary extracted text can never break compilation.
        """
        contact_bits = [_latex_escape(bit) for bit in (location, phone, email) if bit]
        contact = " \\textbullet{} ".join(contact_bits)

        header = (
            f"\\begin{{center}}{{\\LARGE \\textbf{{{_latex_escape(name or 'Curriculum Vitae')}}}}}"
            "\\end{center}"
        )
        if contact:
            header += f"\n\\begin{{center}}\\small {contact}\\end{{center}}"

        body_parts: list[str] = []
        for heading, content in sections:
            rendered = _render_cv_section_body(content)
            if not rendered:
                continue
            body_parts.append(f"\\section*{{{_latex_escape(heading)}}}\n{rendered}")
        body = "\n\n".join(body_parts)

        return (
            _CV_PREAMBLE
            + "\n\\begin{document}\n\n"
            + header
            + "\n\n"
            + body
            + "\n\n\\end{document}\n"
        )


_CV_PREAMBLE = textwrap.dedent(
    r"""
    \documentclass[11pt]{article}
    \usepackage[a4paper, margin=1in]{geometry}
    \usepackage{parskip}
    \usepackage{enumitem}
    \usepackage{hyperref}
    \pagestyle{empty}
    """
).strip()


def _render_cv_section_body(content: str) -> str:
    """Turn a plain-text section body into safe, compilable LaTeX.

    Blank lines split paragraphs. A multi-line paragraph whose every line looks
    like a bullet ("-", "*", "•") becomes an itemize; otherwise wrapped lines are
    joined into a single paragraph. Everything is escaped so no extracted text
    can break the document.
    """
    paragraphs = re.split(r"\n\s*\n", (content or "").strip())
    rendered: list[str] = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if not lines:
            continue
        is_bullets = len(lines) > 1 and all(ln.lstrip().startswith(("-", "*", "•")) for ln in lines)
        if is_bullets:
            items = "\n".join(rf"\item {_latex_escape(ln.lstrip('-*• ').strip())}" for ln in lines)
            rendered.append("\\begin{itemize}\n" + items + "\n\\end{itemize}")
        else:
            rendered.append(_latex_escape(" ".join(lines)))
    return "\n\n".join(rendered)


def _latex_escape(text: str) -> str:
    """Escape LaTeX special characters in plain-text input."""
    if not text:
        return ""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = text
    # backslash first or it will eat subsequent escapes
    out = out.replace("\\", replacements["\\"])
    for ch, esc in replacements.items():
        if ch == "\\":
            continue
        out = out.replace(ch, esc)
    return out
