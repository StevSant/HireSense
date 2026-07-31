from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from hiresense.opportunities.domain.models import Opportunity, OpportunityKind
from hiresense.opportunities.domain.relevance import (
    is_funded,
    is_stale,
    matches_profile,
    score_opportunity_relevance,
)
from hiresense.opportunities.domain.services import OpportunityIngestionService
from hiresense.opportunities.infrastructure.in_memory_repository import (
    InMemoryOpportunitiesRepository,
)


def _opp(**kwargs) -> Opportunity:
    defaults = {
        "id": uuid4(),
        "kind": OpportunityKind.CONFERENCE,
        "title": "AI Summit",
        "organization": "Org",
        "url": "https://example.com",
        "description": "Python and machine learning",
        "topics": ["python", "ai"],
        "country": "Chile",
        "funding": None,
        "source": "curated",
        "source_id": "x",
        "status": "open",
        "start_date": date.today() + timedelta(days=60),
        "application_deadline": date.today() + timedelta(days=30),
    }
    defaults.update(kwargs)
    return Opportunity(**defaults)


def test_score_opportunity_relevance_counts_distinct_skills() -> None:
    opp = _opp(description="Python and AI with Python workshops")
    score = score_opportunity_relevance(opp, {"python", "ai", "rust"})
    assert score == 1.0  # topic python+ai (0.9) + text tokens, capped


def test_score_handles_qualified_profile_skills_and_compound_titles() -> None:
    opp = _opp(
        title="DjangoCon US",
        topics=["python"],
        description="Conference focused on python.",
    )
    score = score_opportunity_relevance(
        opp,
        {"Python (principal)", "Django", "Django REST Framework"},
    )
    assert score is not None
    assert score >= 0.45


def test_is_funded_for_grants_and_explicit_funding() -> None:
    assert is_funded(_opp(kind=OpportunityKind.GRANT, funding=None)) is True
    assert is_funded(_opp(funding="Travel covered")) is True
    assert is_funded(_opp(funding="none")) is False


def test_is_stale_for_past_deadlines_and_events() -> None:
    assert is_stale(_opp(application_deadline=date.today() - timedelta(days=1))) is True
    assert is_stale(_opp(cfp_deadline=date.today() + timedelta(days=1))) is False
    assert (
        is_stale(
            _opp(
                application_deadline=None,
                cfp_deadline=None,
                start_date=date.today() - timedelta(days=2),
                end_date=None,
            )
        )
        is True
    )


def test_matches_profile_drops_unrelated_stack_topics() -> None:
    php = _opp(title="Dutch PHP Conference", topics=["php"], description="PHP frameworks")
    assert matches_profile(php, {"python", "ai"}) is False
    assert matches_profile(php, {"php", "laravel"}) is True
    assert matches_profile(_opp(topics=["general"]), {"python"}) is True
    assert matches_profile(_opp(funding="Travel covered", topics=["php"]), {"python"}) is True


def test_service_filters_and_relevance_sort() -> None:
    repo = InMemoryOpportunitiesRepository()
    repo.bulk_upsert(
        [
            _opp(
                title="Khipu",
                source_id="khipu",
                topics=["ai", "latam"],
                funding="Travel covered",
                description="AI research",
            ),
            _opp(
                title="RustConf",
                source_id="rustconf",
                topics=["rust"],
                description="Systems programming",
                application_deadline=date.today() + timedelta(days=10),
                start_date=date.today() + timedelta(days=40),
            ),
            _opp(
                title="Expired CFP",
                source_id="expired",
                topics=["ai"],
                application_deadline=date.today() - timedelta(days=5),
            ),
        ]
    )
    service = OpportunityIngestionService(sources=[], normalizers={}, repository=repo)

    funded = service.list(funded_only=True, candidate_skills=["ai"])
    assert len(funded) == 1
    assert funded[0][0].title == "Khipu"
    assert funded[0][1] is not None
    assert funded[0][1] >= 0.45

    by_q = service.list(q="rust")
    assert [o.title for o, _ in by_q] == ["RustConf"]

    by_topics = service.list(topics=["ai", "latam"])
    assert [o.title for o, _ in by_topics] == ["Khipu"]

    assert service.count(hide_stale=True) == 2
    assert service.count(hide_stale=False) == 3

    matched = service.list(matched_only=True, candidate_skills=["ai", "python"])
    assert [o.title for o, _ in matched] == ["Khipu"]

    ranked = service.list(sort="match_desc", candidate_skills=["ai", "python"])
    assert ranked[0][0].title == "Khipu"
    assert ranked[0][1] is not None

    by_title = service.list(sort="title_asc", matched_only=False)
    assert [o.title for o, _ in by_title] == sorted(o.title for o, _ in by_title)
