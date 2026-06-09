import pytest

from hiresense.kernel import LRUCache


def test_get_and_set() -> None:
    cache: LRUCache[str, int] = LRUCache(2)
    cache["a"] = 1
    assert cache.get("a") == 1
    assert cache.get("missing") is None
    assert cache.get("missing", 0) == 0


def test_evicts_least_recently_used() -> None:
    cache: LRUCache[str, int] = LRUCache(2)
    cache["a"] = 1
    cache["b"] = 2
    cache.get("a")  # refresh "a" — "b" is now LRU
    cache["c"] = 3
    assert "a" in cache
    assert "b" not in cache
    assert "c" in cache
    assert len(cache) == 2


def test_overwrite_refreshes_recency() -> None:
    cache: LRUCache[str, int] = LRUCache(2)
    cache["a"] = 1
    cache["b"] = 2
    cache["a"] = 10
    cache["c"] = 3
    assert cache.get("a") == 10
    assert "b" not in cache


def test_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError, match="max_size"):
        LRUCache(0)
