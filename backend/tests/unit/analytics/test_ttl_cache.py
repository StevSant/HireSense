from hiresense.analytics.domain import TtlCache


def test_caches_within_ttl_and_recomputes_after():
    now = {"t": 1000.0}
    cache = TtlCache(ttl_seconds=5, clock=lambda: now["t"])
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return calls["n"]

    assert cache.get_or_compute("k", compute) == 1
    now["t"] = 1004.0
    assert cache.get_or_compute("k", compute) == 1  # within ttl → cached
    assert calls["n"] == 1
    now["t"] = 1006.0
    assert cache.get_or_compute("k", compute) == 2  # ttl expired → recompute
    assert calls["n"] == 2
