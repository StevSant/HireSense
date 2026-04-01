from hiresense.profile.domain.latex_parser import LaTeXParser


SAMPLE_TEX = r"""
\documentclass[11pt, a4paper]{article}
\usepackage{hyperref}
\begin{document}

\begin{center}
{\LARGE \textbf{BRYAN STEVEN MENOSCAL SANTANA}}
\end{center}

\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} l l}
\textbf{Location:} Ecuador, Manabí, Manta & \textbf{Phone:} +593 99 739 9441 \\
\textbf{Email:} \href{mailto:bryanmenoscal2005@gmail.com}{bryanmenoscal2005@gmail.com}
& \textbf{Portfolio:} \href{https://stevsant.vercel.app}{stevsant.vercel.app} \\
\textbf{LinkedIn:} \href{https://linkedin.com/in/bryanmenoscal26}{linkedin.com/in/bryanmenoscal26}
& \textbf{GitHub:} \href{https://github.com/StevSant}{github.com/StevSant} \\
\end{tabular*}

\section*{SUMMARY}

Backend Engineer focused on designing scalable, event-driven systems using Python (FastAPI, Django REST).

\section*{TECHNICAL SKILLS}
\begin{tabular}{p{0.25\textwidth} p{0.7\textwidth}}
\textbf{Backend:} & Django, Flask, FastAPI, NestJS \\
\textbf{Languages:} & Python, Golang, TypeScript \\
\textbf{Databases:} & MySQL, PostgreSQL, MongoDB \\
\end{tabular}

\section*{PROJECTS \& RELEVANT EXPERIENCE}

\textbf{STREAMFLOWMUSIC} \hfill Personal Project \\
\textit{Backend Developer} \hfill 2025

\begin{itemize}
\item Developed a scalable REST API using Django REST Framework.
\item Implemented asynchronous background tasks for media ingestion.
\end{itemize}

\section*{EDUCATION}

\textbf{UNIVERSIDAD LAICA ELOY ALFARO DE MANABÍ} \hfill Ecuador \\
\textit{BSc. in Software Engineering} \hfill 2023 -- Present

\end{document}
"""


def test_parse_extracts_name() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.name == "BRYAN STEVEN MENOSCAL SANTANA"


def test_parse_extracts_email() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.email == "bryanmenoscal2005@gmail.com"


def test_parse_extracts_phone() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.phone == "+593 99 739 9441"


def test_parse_extracts_location() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.location == "Ecuador, Manabí, Manta"


def test_parse_extracts_sections() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    section_names = [s.name for s in result.sections]
    assert "SUMMARY" in section_names
    assert "TECHNICAL SKILLS" in section_names
    assert "PROJECTS & RELEVANT EXPERIENCE" in section_names
    assert "EDUCATION" in section_names


def test_parse_section_content_not_empty() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    for section in result.sections:
        assert len(section.content.strip()) > 0


def test_parse_preserves_raw_tex() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.raw_tex == SAMPLE_TEX
