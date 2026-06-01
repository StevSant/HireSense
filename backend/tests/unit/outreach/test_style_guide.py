from hiresense.outreach.domain.style_guide import DEFAULT_STYLE_GUIDE, load_style_guide


def test_loads_existing_file(tmp_path):
    p = tmp_path / "style.md"
    p.write_text("Be concise and specific.", encoding="utf-8")
    assert load_style_guide(str(p)) == "Be concise and specific."


def test_missing_file_returns_default():
    assert load_style_guide("does/not/exist.md") == DEFAULT_STYLE_GUIDE
