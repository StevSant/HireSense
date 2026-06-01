from hiresense.analytics.domain import SalaryParser


def test_parses_annual_range_usd():
    p = SalaryParser()
    r = p.parse("$100,000 - $120,000 per year")
    assert r is not None
    assert r.currency == "USD"
    assert r.min_annual == 100000
    assert r.max_annual == 120000


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
