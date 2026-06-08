from hiresense.admin.domain import UsageAggregator, UsageRecord


class _FakeRepo:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def list_recent(self, *, limit, offset, provider, model, feature_key, since, sort=None):
        self.calls.append(limit)
        # Return exactly `limit` synthetic records so we can also assert bounding.
        return [
            UsageRecord(
                feature_key="f",
                provider="anthropic",
                model="m",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                latency_ms=0.0,
                success=True,
                error=None,
                user_id=None,
                created_at=None,
                id=None,
            )
            for _ in range(limit)
        ]


def test_recent_calls_uses_config_default_when_no_limit():
    repo = _FakeRepo()
    agg = UsageAggregator(repo=repo, recent_limit=100)

    rows = agg.recent_calls()

    # The config-driven default (100) is threaded to the repo, not a hardcoded 50.
    assert repo.calls == [100]
    assert len(rows) == 100


def test_recent_calls_explicit_limit_overrides_default():
    repo = _FakeRepo()
    agg = UsageAggregator(repo=repo, recent_limit=100)

    rows = agg.recent_calls(limit=7)

    assert repo.calls == [7]
    assert len(rows) == 7
