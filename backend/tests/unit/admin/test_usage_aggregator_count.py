from datetime import datetime, timezone

from hiresense.admin.domain import UsageAggregator


class _CountingRepo:
    def __init__(self, total: int = 0) -> None:
        self.total = total
        self.count_kwargs: dict | None = None

    def count_recent(self, *, provider, model, feature_key, since, until=None) -> int:
        self.count_kwargs = {
            "provider": provider,
            "model": model,
            "feature_key": feature_key,
            "since": since,
        }
        return self.total


def test_count_recent_calls_returns_the_repo_total():
    repo = _CountingRepo(total=437)
    agg = UsageAggregator(repo=repo, recent_limit=100)

    assert agg.count_recent_calls() == 437


def test_count_recent_calls_passes_filters_through_unchanged():
    repo = _CountingRepo()
    agg = UsageAggregator(repo=repo, recent_limit=100)

    agg.count_recent_calls(provider="anthropic", model="m", feature_key="matching")

    assert repo.count_kwargs == {
        "provider": "anthropic",
        "model": "m",
        "feature_key": "matching",
        "since": None,
    }


def test_count_recent_calls_translates_days_into_a_since_cutoff():
    repo = _CountingRepo()
    agg = UsageAggregator(repo=repo, recent_limit=100)

    agg.count_recent_calls(days=7)

    since = repo.count_kwargs["since"]
    assert since is not None
    elapsed_days = (datetime.now(timezone.utc) - since).total_seconds() / 86400
    assert 6.9 < elapsed_days < 7.1
