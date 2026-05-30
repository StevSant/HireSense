from __future__ import annotations

import uuid
from typing import Any, Protocol

from hiresense.profile.domain.models import CandidateProfile


class ProfileRepositoryPort(Protocol):
    def get_by_id(self, id: uuid.UUID) -> CandidateProfile | None: ...

    def get_latest(self, language: str | None = None) -> CandidateProfile | None: ...

    def list_all(self) -> list[CandidateProfile]: ...

    def create(
        self, profile: CandidateProfile, *, original_filename: str | None = None
    ) -> CandidateProfile: ...

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> CandidateProfile | None: ...

    def update_all(self, fields: dict[str, Any]) -> int: ...
