from hiresense.analytics.domain import SalaryParser


def test_parses_annual_range_usd():
    p = SalaryParser()
    r = p.parse("$100,000 - $120,000 per year")
    assert r is not None
    assert r.currency == "USD"
    assert r.min_annual == 100000
    assert r.max_annual == 120000


def test_parses_millions_suffix():
    r = SalaryParser().parse("$1.2m")
    assert r is not None
    assert r.currency == "USD"
    assert r.min_annual == 1_200_000
    assert r.max_annual == 1_200_000


def test_parses_k_suffix_eur():
    r = SalaryParser().parse("€80k–€100k")
    assert r is not None
    assert r.currency == "EUR"
    assert r.min_annual == 80000
    assert r.max_annual == 100000


def test_parses_single_value_gbp():
    r = SalaryParser().parse("£90,000")
    assert r is not None and r.currency == "GBP"
    assert r.min_annual == 90000 and r.max_annual == 90000


def test_normalizes_hourly_to_annual():
    r = SalaryParser().parse("$50/hour")
    assert r is not None and r.currency == "USD"
    assert r.min_annual == 50 * 2080  # 104000


def test_normalizes_monthly_to_annual():
    r = SalaryParser().parse("$8,000/month")
    assert r is not None and r.min_annual == 8000 * 12


def test_unparseable_returns_none():
    p = SalaryParser()
    assert p.parse("competitive") is None
    assert p.parse("") is None
    assert p.parse(None) is None


def test_labeled_monthly_sets_period_and_annualizes():
    r = SalaryParser().parse("USD 2300-2500/mo")
    assert r is not None
    assert r.period == "monthly"
    assert r.min_annual == 27600  # 2300 * 12
    assert r.max_annual == 30000  # 2500 * 12


def test_labeled_hourly_sets_period():
    r = SalaryParser().parse("$50/hour")
    assert r is not None
    assert r.period == "hourly"
    assert r.min_annual == 104000  # 50 * 2080


def test_unlabeled_low_figure_inferred_monthly():
    # Below the floor, no period keyword -> inferred monthly.
    r = SalaryParser(annual_floor=12000).parse("USD 2500")
    assert r is not None
    assert r.period == "monthly"
    assert r.min_annual == 30000  # 2500 * 12


def test_unlabeled_plausible_figure_is_unknown_annual():
    # Above the floor, no keyword -> assumed annual, flagged unknown.
    r = SalaryParser(annual_floor=12000).parse("USD 90,000")
    assert r is not None
    assert r.period == "unknown"
    assert r.min_annual == 90000
    assert r.max_annual == 90000


def test_unlabeled_range_uses_min_for_floor_decision():
    # A range whose LOWEST figure is below the floor is treated as monthly.
    r = SalaryParser(annual_floor=12000).parse("USD 2500-2800")
    assert r is not None
    assert r.period == "monthly"
    assert r.min_annual == 30000  # 2500 * 12
    assert r.max_annual == 33600  # 2800 * 12
