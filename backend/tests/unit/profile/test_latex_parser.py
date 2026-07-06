from hiresense.profile.domain.latex_parser import LaTeXParser


SAMPLE_TEX = r"""
\documentclass[11pt, a4paper]{article}
\usepackage{hyperref}
\begin{document}

\begin{center}
{\LARGE \textbf{JANE DOE}}
\end{center}

\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} l l}
\textbf{Location:} Springfield, Illinois & \textbf{Phone:} +1 555 010 0000 \\
\textbf{Email:} \href{mailto:jane.doe@example.com}{jane.doe@example.com}
& \textbf{Portfolio:} \href{https://janedoe.example.com}{janedoe.example.com} \\
\textbf{LinkedIn:} \href{https://linkedin.com/in/janedoe}{linkedin.com/in/janedoe}
& \textbf{GitHub:} \href{https://github.com/janedoe}{github.com/janedoe} \\
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
    assert result.name == "JANE DOE"


def test_parse_extracts_email() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.email == "jane.doe@example.com"


def test_parse_extracts_phone() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.phone == "+1 555 010 0000"


def test_parse_extracts_location() -> None:
    parser = LaTeXParser()
    result = parser.parse(SAMPLE_TEX)
    assert result.location == "Springfield, Illinois"


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
