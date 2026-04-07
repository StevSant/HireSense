from __future__ import annotations

from bs4 import BeautifulSoup


def strip_html(html: str) -> str:
    """Convert HTML to plain text, preserving paragraph breaks."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["p", "br", "div", "li"]):
        tag.insert_before("\n")
    text = soup.get_text()
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
