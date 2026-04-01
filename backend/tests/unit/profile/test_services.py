import pytest
from hiresense.profile.domain.services import ProfileService
from hiresense.profile.domain.latex_parser import LaTeXParser
from hiresense.profile.domain.skill_extractor import SkillExtractor


SAMPLE_TEX = r"""
\documentclass{article}
\begin{document}

\begin{center}
{\LARGE \textbf{JOHN DOE}}
\end{center}

\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} l l}
\textbf{Email:} \href{mailto:john@example.com}{john@example.com}
& \textbf{Phone:} +1 555 1234 \\
\textbf{Location:} New York, USA & \\
\end{tabular*}

\section*{SUMMARY}
Experienced backend engineer with Python and FastAPI expertise.

\section*{TECHNICAL SKILLS}
\begin{tabular}{p{0.25\textwidth} p{0.7\textwidth}}
\textbf{Backend:} & Python, FastAPI, Django \\
\textbf{Databases:} & PostgreSQL, Redis \\
\end{tabular}

\section*{EDUCATION}
BSc Computer Science

\end{document}
"""


@pytest.mark.asyncio
async def test_profile_service_parse_and_create() -> None:
    parser = LaTeXParser()
    extractor = SkillExtractor()
    service = ProfileService(parser=parser, skill_extractor=extractor)
    profile = await service.parse_and_create(SAMPLE_TEX, language="en")
    assert profile.name == "JOHN DOE"
    assert profile.email == "john@example.com"
    assert len(profile.sections) > 0
    assert len(profile.skills) > 0
    assert "Python" in profile.skills or "python" in [s.lower() for s in profile.skills]


@pytest.mark.asyncio
async def test_profile_service_get_profile() -> None:
    parser = LaTeXParser()
    extractor = SkillExtractor()
    service = ProfileService(parser=parser, skill_extractor=extractor)
    created = await service.parse_and_create(SAMPLE_TEX)
    retrieved = await service.get_profile(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "JOHN DOE"


@pytest.mark.asyncio
async def test_profile_service_get_nonexistent() -> None:
    parser = LaTeXParser()
    extractor = SkillExtractor()
    service = ProfileService(parser=parser, skill_extractor=extractor)
    result = await service.get_profile("nonexistent-id")
    assert result is None
