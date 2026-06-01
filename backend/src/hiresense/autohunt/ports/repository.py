from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.autohunt.domain import Digest


class DigestRepositoryPort(Protocol):
    def add(self, digest: Digest) -> Digest: ...

    def latest(self) -> Digest | None: ...

    def list_recent(self, limit: int) -> list[Digest]: ...

    def prune_older_than(self, cutoff: datetime) -> int: ...
