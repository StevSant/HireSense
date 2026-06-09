from __future__ import annotations

from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Minimal bounded mapping with least-recently-used eviction.

    Drop-in for the dict-style `get`/`__setitem__`/`__contains__` usage of the
    embedding caches; not thread-safe on its own (callers already serialize
    behind an asyncio.Lock where it matters).
    """

    def __init__(self, max_size: int) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max_size = max_size
        self._data: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K, default: V | None = None) -> V | None:
        if key not in self._data:
            return default
        self._data.move_to_end(key)
        return self._data[key]

    def __setitem__(self, key: K, value: V) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)
