from __future__ import annotations

from bs4 import BeautifulSoup

# Hard cap on input length before parsing. Every description runs through a full
# BeautifulSoup parse once per field per job during bulk ingestion of thousands
# of jobs; an unbounded (or adversarial) document turns that parse into a CPU /
# memory sink. 200k chars comfortably fits any real posting while bounding the
# worst case. A code-level safety invariant, in the spirit of MAX_PAGES.
MAX_HTML_CHARS = 200_000


def strip_html(html: str, *, max_chars: int = MAX_HTML_CHARS) -> str:
    """Convert HTML to plain text, preserving paragraph breaks.

    Input is truncated to ``max_chars`` before parsing to bound CPU/memory on
    unbounded or adversarial documents.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html[:max_chars], "html.parser")
    for tag in soup.find_all(["p", "br", "div", "li"]):
        tag.insert_before("\n")
    text = soup.get_text()
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
