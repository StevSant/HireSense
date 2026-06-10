from hiresense.portfolio.domain import PortfolioProject, ProjectText, RelevantProjectSelector


def _project(key, *, tech=None, title=None, pinned=False, position=None):
    return PortfolioProject(
        id=key, source="supabase", source_key=key, pinned=pinned, position=position,
        tech=tech or [],
        translations={"en": ProjectText(title=title or key, description="d")},
    )


def test_ranks_by_term_overlap_and_drops_irrelevant() -> None:
    selector = RelevantProjectSelector()
    projects = [
        _project("nest", tech=["nestjs", "kafka"]),
        _project("ai", tech=["fastapi", "langchain", "postgresql"]),
        _project("unrelated", tech=["unity", "csharp"]),
    ]
    picked = selector.select(
        job_skills=["FastAPI", "PostgreSQL"],
        job_text="We use LangChain agents over Postgres.",
        projects=projects,
        top_n=2,
    )
    assert [p.source_key for p in picked] == ["ai"]  # zero-overlap projects are dropped


def test_title_tokens_count_and_pinned_breaks_ties() -> None:
    selector = RelevantProjectSelector()
    projects = [
        _project("b", tech=["python"], position=2),
        _project("a", tech=["python"], pinned=True, position=9),
    ]
    picked = selector.select(job_skills=["python"], job_text="", projects=projects, top_n=2)
    assert [p.source_key for p in picked] == ["a", "b"]  # equal score -> pinned first

    titled = selector.select(
        job_skills=[], job_text="building a kafka pipeline",
        projects=[_project("k", title="kafka-dashboard"), _project("x", title="todo-app")],
        top_n=2,
    )
    assert [p.source_key for p in titled] == ["k"]


def test_top_n_caps_results() -> None:
    selector = RelevantProjectSelector()
    projects = [_project(f"p{i}", tech=["python"]) for i in range(5)]
    assert len(selector.select(job_skills=["python"], job_text="", projects=projects, top_n=2)) == 2
