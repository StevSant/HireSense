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
        match = re.search(r"\\textbf\{Phone:\}\s*([^\\\n&]+)", tex)
        return match.group(1).strip() if match else None

    def _extract_location(self, tex: str) -> str | None:
        match = re.search(r"\\textbf\{Location:\}\s*([^\\\n&]+)", tex)
        return match.group(1).strip() if match else None

    def _extract_sections(self, tex: str) -> list[ParsedSection]:
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
