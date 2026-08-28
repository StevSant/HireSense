from __future__ import annotations

from pydantic import BaseModel, Field


class PdfInspection(BaseModel):
    valid: bool = False
    pages: int = 0
    text_chars: int = 0
    has_text_layer: bool = False
    warnings: list[str] = Field(default_factory=list)


def inspect_pdf(file_bytes: bytes) -> PdfInspection:
    """Inspect a generated PDF without trusting its producer or filename."""
    if not file_bytes:
        return PdfInspection(warnings=["PDF is empty."])
    try:
        import pymupdf

        document = pymupdf.open(stream=file_bytes, filetype="pdf")
        try:
            pages = len(document)
            text_chars = 0
            for page in document:
                page_text = page.get_text()
                if isinstance(page_text, str):
                    text_chars += len(page_text.strip())
        finally:
            document.close()
    except Exception:  # noqa: BLE001 - malformed PDFs become a report, not a crash
        return PdfInspection(warnings=["PDF could not be parsed."])
    warnings: list[str] = []
    if pages == 0:
        warnings.append("PDF contains no pages.")
    if text_chars == 0:
        warnings.append("PDF has no extractable text layer.")
    return PdfInspection(
        valid=pages > 0,
        pages=pages,
        text_chars=text_chars,
        has_text_layer=text_chars > 0,
        warnings=warnings,
    )
