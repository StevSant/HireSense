from hiresense.research.domain.models import CompanyResearch


def test_company_research_creation() -> None:
    research = CompanyResearch(
        company_name="anthropic", funding_stage="Series D",
        tech_stack="Python, Rust", culture_summary="AI safety focused",
        growth_trajectory="Rapid growth", red_flags=None,
        pros="Great mission", cons="High intensity", raw_llm_response="{}",
    )
    assert research.company_name == "anthropic"
    assert research.funding_stage == "Series D"
    assert research.red_flags is None


def test_company_research_all_fields() -> None:
    research = CompanyResearch(
        company_name="startup", funding_stage="Seed",
        tech_stack="Node.js", culture_summary="Fast-paced",
        growth_trajectory="Early stage", red_flags="High burn rate",
        pros="Equity upside", cons="Unstable", raw_llm_response="{}",
    )
    assert research.red_flags == "High burn rate"
