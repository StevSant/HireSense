from hiresense.applications.domain.pdf_quality import inspect_pdf


def test_inspect_pdf_reports_empty_bytes() -> None:
    report = inspect_pdf(b"")
    assert report.valid is False
    assert "empty" in report.warnings[0].lower()


def test_inspect_pdf_reports_malformed_bytes() -> None:
    report = inspect_pdf(b"not a pdf")
    assert report.valid is False
    assert report.has_text_layer is False
