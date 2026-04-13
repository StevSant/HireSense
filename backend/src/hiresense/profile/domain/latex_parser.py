from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    name: str
    content: str


@dataclass
class ParsedCV:
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    sections: list[ParsedSection] = field(default_factory=list)
    raw_tex: str = ""


class LaTeXParser:
    def parse(self, tex_content: str) -> ParsedCV:
        name = self._extract_name(tex_content)
        email = self._extract_email(tex_content)
        phone = self._extract_phone(tex_content)
        location = self._extract_location(tex_content)
        sections = self._extract_sections(tex_content)
        return ParsedCV(
            name=name,
            email=email,
            phone=phone,
            location=location,
            sections=sections,
            raw_tex=tex_content,
        )

    def _extract_name(self, tex: str) -> str:
        match = re.search(r"\\LARGE\s*\\textbf\{([^}]+)\}", tex)
        if match:
            return match.group(1).strip()
        match = re.search(
            r"\\begin\{center\}.*?\\textbf\{([^}]+)\}", tex, re.DOTALL
        )
        return match.group(1).strip() if match else ""

    def _extract_email(self, tex: str) -> str | None:
        match = re.search(r"\\href\{mailto:([^}]+)\}", tex)
        return match.group(1).strip() if match else None

    def _extract_phone(self, tex: str) -> str | None:
        patterns = [
            r"\\textbf\{(?:Phone|Tel[eé]fono|Tel):\}\s*([^\\\n&]+)",
            r"(?:Phone|Tel[eé]fono|Tel):\s*([+\d\s()-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, tex, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_location(self, tex: str) -> str | None:
        patterns = [
            r"\\textbf\{(?:Location|Ubicaci[oó]n|Direcci[oó]n):\}\s*([^\\\n&]+)",
            r"(?:Location|Ubicaci[oó]n|Direcci[oó]n):\s*([^\\\n&]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, tex, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_sections(self, tex: str) -> list[ParsedSection]:
        """Extract sections with raw LaTeX content (for skill extraction)."""
        pattern = r"\\section\*\{([^}]+)\}"
        splits = re.split(pattern, tex)
        sections: list[ParsedSection] = []
        for i in range(1, len(splits) - 1, 2):
            section_name = splits[i].strip().replace("\\&", "&")
            content = splits[i + 1].strip()
            content = re.sub(r"\\end\{document\}", "", content).strip()
            if content:
                sections.append(ParsedSection(name=section_name, content=content))
        return sections

    def strip_section_content(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        """Return new sections with LaTeX commands stripped to plain text."""
        result = []
        for section in sections:
            cleaned = self._strip_latex(section.content)
            if cleaned:
                result.append(ParsedSection(name=section.name, content=cleaned))
        return result

    def _strip_latex(self, tex: str) -> str:
        """Convert raw LaTeX content to readable plain text."""
        text = tex

        # Remove comment lines (% ...)
        text = re.sub(r"(?m)^%.*$", "", text)
        text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)

        # Extract tabular content: convert rows to readable lines
        text = self._convert_tabulars(text)

        # Remove environments (begin/end)
        text = re.sub(r"\\begin\{[^}]*\}(?:\{[^}]*\})*", "", text)
        text = re.sub(r"\\end\{[^}]*\}", "", text)

        # Convert formatting commands to their content
        text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\textit\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\underline\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\textsc\{([^}]*)\}", r"\1", text)

        # Convert hyperlinks
        text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\url\{([^}]*)\}", r"\1", text)

        # Remove spacing/layout commands
        text = re.sub(r"\\[vh]space\{[^}]*\}", "", text)
        text = re.sub(r"\\(?:small|large|Large|LARGE|huge|Huge|normalsize|footnotesize|scriptsize|tiny)\b", "", text)
        text = re.sub(r"\\(?:hrule|hline|noindent|newpage|clearpage|pagebreak)\b", "", text)
        text = re.sub(r"\\(?:hfill|vfill)\b", "", text)

        # Remove \item and convert to bullet-like
        text = re.sub(r"\\item\b\s*", "- ", text)

        # Row separators
        text = text.replace("\\\\", "\n")

        # Escaped special characters
        text = text.replace("\\&", "&")
        text = text.replace("\\%", "%")
        text = text.replace("\\$", "$")
        text = text.replace("\\#", "#")
        text = text.replace("\\_", "_")
        text = text.replace("\\~", "~")

        # Remove remaining unknown commands (e.g., \centering, \raggedright)
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\{[^}]*\})*", "", text)

        # Clean up ampersands (tabular column separators that weren't in a tabular)
        text = re.sub(r"\s*&\s*", " — ", text)

        # Clean up whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        return text

    def _convert_tabulars(self, tex: str) -> str:
        """Convert \\begin{tabular}...\\end{tabular} blocks to plain text."""

        def _tabular_to_text(match: re.Match[str]) -> str:
            body = match.group(1)
            rows = re.split(r"\\\\", body)
            lines = []
            for row in rows:
                row = row.strip()
                if not row or row == "\\hline":
                    continue
                # Split columns by &
                cols = [c.strip() for c in row.split("&")]
                # Strip LaTeX from each cell
                cleaned = []
                for col in cols:
                    col = re.sub(r"\\textbf\{([^}]*)\}", r"\1", col)
                    col = re.sub(r"\\textit\{([^}]*)\}", r"\1", col)
                    col = col.strip()
                    if col:
                        cleaned.append(col)
                if cleaned:
                    lines.append(" — ".join(cleaned))
            return "\n".join(lines)

        # Match \begin{tabular}{...} with arbitrarily nested braces in the column spec
        return re.sub(
            r"\\begin\{tabular\}(?:\{(?:[^{}]|\{[^{}]*\})*\})+(.*?)\\end\{tabular\}",
            _tabular_to_text,
            tex,
            flags=re.DOTALL,
        )
