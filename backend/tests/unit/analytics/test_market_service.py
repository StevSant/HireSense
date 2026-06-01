from datetime import datetime, timezone

from hiresense.analytics.domain import MarketIntelService, SalaryParser, SkillNormalizer


class _FakeCorpus:
    def open_skill_lists(self):
        return [["Python", "React"], ["python", "Go"], ["PYTHON"]]

    def remote_modality_counts(self):
        return {"remote": 5, "on_site": 3, "hybrid": 2}

    def posting_dates(self):
        return [datetime(2026, 5, 1, tzinfo=timezone.utc), datetime(2026, 5, 2, tzinfo=timezone.utc),
                datetime(2026, 5, 9, tzinfo=timezone.utc)]

    def open_salary_strings(self):
        return (["$100k-$120k", "$90k", "competitive"], 4)

    def salary_strings_for_ids(self, ids):
        return {}


def _svc():
    return MarketIntelService(_FakeCorpus(), SkillNormalizer(), SalaryParser())


def test_top_skills_normalized_and_counted():
    intel = _svc().compute(top_skills=10)
    top = {s.skill: s.count for s in intel.top_skills}
    assert top["python"] == 3  # Python/python/PYTHON collapse
    assert top["react"] == 1


def test_remote_mix_passthrough():
    intel = _svc().compute(top_skills=10)
    assert intel.remote_mix["remote"] == 5


def test_salary_distribution_dominant_currency():
    intel = _svc().compute(top_skills=10)
    d = intel.salary_distribution
    assert d.currency == "USD"
    assert d.parsed_count == 2 and d.unparsed_count == 1
    # True bounds across postings: min-of-mins=90000, max-of-maxes=120000.
    assert d.min_annual == 90000 and d.max_annual == 120000
    # Median over per-job midpoints: $100k-$120k -> 110000, $90k -> 90000 -> 100000.
    assert d.median_annual == 100000
    # 3 of 4 open postings disclosed a salary string.
    assert d.disclosed_pct == 75.0


def test_weekly_trend_buckets():
    intel = _svc().compute(top_skills=10)
    # 3 postings across 2 ISO weeks
    assert sum(p.count for p in intel.posting_trend) == 3
