from hiresense.ingestion.domain.html_stripper import MAX_HTML_CHARS, strip_html


def test_strips_basic_tags() -> None:
    html = "<p>Hello <b>world</b></p>"
    assert strip_html(html) == "Hello world"


def test_preserves_paragraph_breaks() -> None:
    html = "<p>First paragraph</p><p>Second paragraph</p>"
    result = strip_html(html)
    assert "First paragraph" in result
    assert "Second paragraph" in result
    assert "\n" in result


def test_handles_empty_string() -> None:
    assert strip_html("") == ""


def test_handles_plain_text() -> None:
    assert strip_html("no html here") == "no html here"


def test_strips_nested_tags() -> None:
    html = "<div><ul><li>Item 1</li><li>Item 2</li></ul></div>"
    result = strip_html(html)
    assert "Item 1" in result
    assert "Item 2" in result


def test_decodes_html_entities() -> None:
    html = "<p>Salary &gt; $100k &amp; benefits</p>"
    assert strip_html(html) == "Salary > $100k & benefits"


def test_caps_input_to_max_chars() -> None:
    # Content beyond the cap is never parsed (bounds CPU/memory on huge input).
    keep = "<p>keep</p>"
    html = keep + "<p>DROP</p>" * 100
    result = strip_html(html, max_chars=len(keep))
    assert "keep" in result
    assert "DROP" not in result


def test_default_cap_truncates_oversized_input() -> None:
    oversized = ("a" * MAX_HTML_CHARS) + "SENTINEL_PAST_CAP"
    assert "SENTINEL_PAST_CAP" not in strip_html(oversized)
