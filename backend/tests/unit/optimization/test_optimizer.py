import pytest
from hiresense.optimization.domain.services import CVOptimizer


class FakeLLM:
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        return """{
            "changes": [
                {
                    "section_name": "SUMMARY",
                    "original": "Backend developer with Python experience",
                    "optimized": "Backend engineer specializing in scalable Python APIs with FastAPI and Kubernetes",
                    "reason": "Aligned with job requirements"
                }
            ],
            "improvement_summary": "Optimized summary to highlight relevant FastAPI and cloud experience"
        }"""


@pytest.mark.asyncio
async def test_optimizer_produces_result() -> None:
    optimizer = CVOptimizer(llm=FakeLLM())
    original_tex = r"""
\section*{SUMMARY}
Backend developer with Python experience

\section*{TECHNICAL SKILLS}
\textbf{Backend:} & Python, Django \\
"""
    result = await optimizer.optimize(
        match_id="match-1",
        job_id="job-1",
        cv_id="cv-1",
        original_tex=original_tex,
        job_description="Backend engineer with FastAPI and Kubernetes",
        job_skills=["python", "fastapi", "kubernetes"],
        missing_skills=["fastapi", "kubernetes"],
        recommendations=["Highlight API development experience"],
    )
    assert result.match_id == "match-1"
    assert len(result.changes) > 0
    assert result.changes[0].section_name == "SUMMARY"
    assert result.improvement_summary is not None
    assert result.optimized_tex != result.original_tex


@pytest.mark.asyncio
async def test_optimizer_applies_changes_to_tex() -> None:
    optimizer = CVOptimizer(llm=FakeLLM())
    original_tex = r"""
\section*{SUMMARY}
Backend developer with Python experience

\section*{EDUCATION}
Some education content
"""
    result = await optimizer.optimize(
        match_id="match-2",
        job_id="job-2",
        cv_id="cv-2",
        original_tex=original_tex,
        job_description="Any job",
        job_skills=[],
        missing_skills=[],
        recommendations=[],
    )
    # The optimized tex should have the replacement applied
    assert "Backend engineer specializing" in result.optimized_tex


@pytest.mark.asyncio
async def test_optimizer_parses_markdown_fenced_json() -> None:
    """Claude usually wraps JSON output in ```json ... ``` fences;
    optimizer must strip those before parsing."""

    class FencedLLM:
        async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
            return (
                "```json\n"
                "{\n"
                '  "changes": [\n'
                "    {\n"
                '      "section_name": "SUMMARY",\n'
                '      "original": "Backend developer with Python experience",\n'
                '      "optimized": "Backend SRE with Python, Kubernetes, and Terraform experience",\n'
                '      "reason": "Adds missing required skills"\n'
                "    }\n"
                "  ],\n"
                '  "improvement_summary": "Added Kubernetes and Terraform to summary"\n'
                "}\n"
                "```"
            )

    optimizer = CVOptimizer(llm=FencedLLM())
    result = await optimizer.optimize(
        match_id="match-x",
        job_id="job-x",
        cv_id="cv-x",
        original_tex="\\section*{SUMMARY}\nBackend developer with Python experience",
        job_description="SRE",
        job_skills=["python", "kubernetes"],
        missing_skills=["kubernetes"],
        recommendations=[],
    )
    assert len(result.changes) == 1
    assert result.changes[0].section_name == "SUMMARY"
    assert "Kubernetes" in result.optimized_tex
    assert result.improvement_summary == "Added Kubernetes and Terraform to summary"


@pytest.mark.asyncio
async def test_optimizer_truncates_job_description_in_prompt() -> None:
    class CapturingLLM:
        def __init__(self) -> None:
            self.last_prompt = ""

        async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
            self.last_prompt = prompt
            return '{"changes": [], "improvement_summary": "none"}'

    llm = CapturingLLM()
    optimizer = CVOptimizer(llm=llm, job_char_limit=100)
    await optimizer.optimize(
        match_id="match-cap",
        job_id="job-cap",
        cv_id="cv-cap",
        original_tex="\\section*{SUMMARY}\nSome text",
        job_description="d" * 50_000,
        job_skills=[],
        missing_skills=[],
        recommendations=[],
    )
    prefix = "Job Description: "
    start = llm.last_prompt.index(prefix) + len(prefix)
    end = llm.last_prompt.index("\n", start)
    assert llm.last_prompt[start:end] == "d" * 100


@pytest.mark.asyncio
async def test_optimizer_does_not_truncate_original_tex() -> None:
    """original_tex must stay intact — _apply_changes() replaces exact
    substrings against it, so truncating would break the anchor match."""

    class CapturingLLM:
        def __init__(self) -> None:
            self.last_prompt = ""

        async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
            self.last_prompt = prompt
            return '{"changes": [], "improvement_summary": "none"}'

    llm = CapturingLLM()
    long_tex = "\\section*{SUMMARY}\n" + ("t" * 50_000)
    optimizer = CVOptimizer(llm=llm, job_char_limit=100)
    await optimizer.optimize(
        match_id="match-tex",
        job_id="job-tex",
        cv_id="cv-tex",
        original_tex=long_tex,
        job_description="short",
        job_skills=[],
        missing_skills=[],
        recommendations=[],
    )
    assert long_tex in llm.last_prompt


@pytest.mark.asyncio
async def test_optimizer_handles_llm_failure() -> None:
    class BrokenLLM:
        async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
            raise RuntimeError("LLM is down")

    optimizer = CVOptimizer(llm=BrokenLLM())
    result = await optimizer.optimize(
        match_id="match-3",
        job_id="job-3",
        cv_id="cv-3",
        original_tex="\\section*{SUMMARY}\nSome text",
        job_description="Any",
        job_skills=[],
        missing_skills=[],
        recommendations=[],
    )
    assert result.changes == []
    assert result.optimized_tex == "\\section*{SUMMARY}\nSome text"
