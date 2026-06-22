from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class JobToggleRepository(Protocol):
    """Persistence port for per-job enable/disable state."""

    def is_enabled(self, job_name: str, default: bool) -> bool: ...

    def set_enabled(self, job_name: str, enabled: bool) -> None: ...

    def all_states(self) -> dict[str, bool]: ...
