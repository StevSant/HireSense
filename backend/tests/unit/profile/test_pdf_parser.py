from __future__ import annotations

import pytest

from hiresense.profile.domain.pdf_parser import PDFParser


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


@pytest.mark.asyncio
async def test_pdf_parser_truncates_extracted_text_in_prompt() -> None:
    llm = FakeLLM('{"name": "Jane", "sections": [], "skills": []}')
    parser = PDFParser(llm=llm, char_limit=100)
    parser.extract_text = lambda _file_bytes: "x" * 50_000  # type: ignore[method-assign]

    await parser.parse(b"irrelevant")

    prefix = "Extract structured information from this CV:\n\n"
    start = llm.last_prompt.index(prefix) + len(prefix)
    assert llm.last_prompt[start:] == "x" * 100


@pytest.mark.asyncio
async def test_pdf_parser_default_char_limit_is_20000() -> None:
    llm = FakeLLM('{"name": "Jane", "sections": [], "skills": []}')
    parser = PDFParser(llm=llm)
    parser.extract_text = lambda _file_bytes: "y" * 50_000  # type: ignore[method-assign]

    await parser.parse(b"irrelevant")

    prefix = "Extract structured information from this CV:\n\n"
    start = llm.last_prompt.index(prefix) + len(prefix)
    assert llm.last_prompt[start:] == "y" * 20_000


@pytest.mark.asyncio
async def test_pdf_parser_short_text_is_not_truncated() -> None:
    llm = FakeLLM('{"name": "Jane", "sections": [], "skills": []}')
    parser = PDFParser(llm=llm, char_limit=100)
    parser.extract_text = lambda _file_bytes: "short cv text"  # type: ignore[method-assign]

    await parser.parse(b"irrelevant")

    assert "short cv text" in llm.last_prompt


@pytest.mark.asyncio
async def test_pdf_parser_stores_full_raw_text_untruncated() -> None:
    """The char_limit only bounds what's sent to the LLM prompt — the
    fallback/stored raw_tex on ParsedCV must keep the full extracted text."""
    llm = FakeLLM('{"name": "Jane", "sections": [], "skills": []}')
    parser = PDFParser(llm=llm, char_limit=100)
    long_text = "z" * 50_000
    parser.extract_text = lambda _file_bytes: long_text  # type: ignore[method-assign]

    parsed = await parser.parse(b"irrelevant")

    assert parsed.raw_tex == long_text
