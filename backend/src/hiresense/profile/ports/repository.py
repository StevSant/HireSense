from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.profile.domain.models import Profile


class ProfileRepositoryPort(Protocol):
    def get_by_id(self, id: uuid.UUID) -> Profile | None: ...

    def get_latest(self) -> Profile | None: ...

    def create(self, profile: Profile) -> Profile: ...
