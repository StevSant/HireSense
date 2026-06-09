from hiresense.portfolio.domain import PortfolioProject, ProjectText


def _project(**over) -> PortfolioProject:
    base = dict(
        id="p1",
        source="supabase",
        source_key="hiresense",
        tech=["python", "angular"],
        translations={
            "en": ProjectText(title="HireSense", description="AI job hunting"),
            "es": ProjectText(title="HireSense ES", description="Caza de empleo con IA"),
        },
    )
    base.update(over)
    return PortfolioProject(**base)


def test_text_for_prefers_requested_language() -> None:
    assert _project().text_for("es").title == "HireSense ES"


def test_text_for_falls_back_to_english_then_any() -> None:
    assert _project().text_for("fr").title == "HireSense"
    only_es = _project(translations={"es": ProjectText(title="Solo ES")})
    assert only_es.text_for("fr").title == "Solo ES"


def test_text_for_none_when_no_translations() -> None:
    assert _project(translations={}).text_for("en") is None
