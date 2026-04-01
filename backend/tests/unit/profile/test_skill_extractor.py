import pytest

from hiresense.profile.domain.skill_extractor import SkillExtractor


SKILLS_SECTION_CONTENT = r"""
\begin{tabular}{p{0.25\textwidth} p{0.7\textwidth}}
\textbf{Backend:} & Django, Flask, FastAPI, NestJS, Kafka, RabbitMQ, LangChain \\
\textbf{Languages:} & Python, Golang, TypeScript \\
\textbf{Cloud \& DevOps:} & Google Cloud Run, Azure, Vercel \\
\textbf{Databases:} & MySQL, PostgreSQL, MongoDB \\
\textbf{Testing:} & PyTest, Unit Testing, Integration Testing \\
\textbf{Tools:} & Git, Docker, Kubernetes \\
\end{tabular}
"""


class FakeLLM:
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        return '["python", "fastapi", "django", "postgresql", "docker"]'


def test_extract_skills_from_tabular() -> None:
    extractor = SkillExtractor()
    skills = extractor.extract_from_tabular(SKILLS_SECTION_CONTENT)
    assert "Django" in skills
    assert "FastAPI" in skills
    assert "Python" in skills
    assert "PostgreSQL" in skills
    assert "Docker" in skills
    assert len(skills) > 10


def test_extract_skills_deduplicates() -> None:
    extractor = SkillExtractor()
    content = r"""
    \textbf{Backend:} & Python, FastAPI \\
    \textbf{Languages:} & Python, TypeScript \\
    """
    skills = extractor.extract_from_tabular(content)
    python_count = sum(1 for s in skills if s.lower() == "python")
    assert python_count == 1


@pytest.mark.asyncio
async def test_extract_with_llm() -> None:
    extractor = SkillExtractor(llm=FakeLLM())
    skills = await extractor.extract_with_llm(
        "Backend engineer with Python and FastAPI experience"
    )
    assert "python" in skills
    assert "fastapi" in skills
