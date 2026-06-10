from hiresense.portfolio.domain import PortfolioProject, ProjectText, portfolio_profile_text


def _project(key: str, *, pinned=False, position=None, tech=None, title=None, desc=None):
    return PortfolioProject(
        id=key,
        source="supabase",
        source_key=key,
        pinned=pinned,
        position=position,
        tech=tech or [],
        translations={"en": ProjectText(title=title or key, description=desc)},
    )


def test_formats_title_tech_and_first_description_line() -> None:
    text = portfolio_profile_text(
        [_project("hs", tech=["python", "fastapi"], title="HireSense", desc="AI job hunt.\nMore.")],
        language="en",
        char_cap=500,
    )
    assert text.startswith("Portfolio projects:")
    assert "- HireSense [python, fastapi]: AI job hunt." in text
    assert "More." not in text


def test_pinned_projects_come_first_then_position() -> None:
    text = portfolio_profile_text(
        [_project("b", position=2), _project("a", position=1), _project("p", pinned=True, position=9)],
        language="en",
        char_cap=500,
    )
    lines = text.splitlines()
    assert [ln[2:] for ln in lines[1:]] == ["p", "a", "b"]


def test_respects_char_cap_and_empty_input() -> None:
    assert portfolio_profile_text([], language="en", char_cap=100) == ""
    text = portfolio_profile_text([_project("x", desc="y" * 500)], language="en", char_cap=50)
    assert len(text) <= 50


def test_cap_smaller_than_header_returns_empty() -> None:
    assert portfolio_profile_text([_project("x")], language="en", char_cap=10) == ""
