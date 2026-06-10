from datetime import datetime, timezone


def test_portfolio_visit_construction_and_defaults() -> None:
    from hiresense.portfolio.domain import PortfolioVisit

    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    visit = PortfolioVisit(ref="hiresense-abc123", first_seen=now, last_seen=now)

    assert visit.ref == "hiresense-abc123"
    assert visit.application_id is None
    assert visit.first_seen == now
    assert visit.last_seen == now
    assert visit.page_views == 0
    assert visit.cv_downloads == 0
    assert visit.country is None
    assert visit.organization is None


def test_portfolio_visit_all_fields() -> None:
    from hiresense.portfolio.domain import PortfolioVisit

    first = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
    last = datetime(2026, 6, 10, 18, 30, 0, tzinfo=timezone.utc)
    visit = PortfolioVisit(
        ref="hiresense-xyz",
        application_id="xyz",
        first_seen=first,
        last_seen=last,
        page_views=5,
        cv_downloads=2,
        country="ES",
        organization="Acme Corp",
    )

    assert visit.application_id == "xyz"
    assert visit.page_views == 5
    assert visit.cv_downloads == 2
    assert visit.country == "ES"
    assert visit.organization == "Acme Corp"
