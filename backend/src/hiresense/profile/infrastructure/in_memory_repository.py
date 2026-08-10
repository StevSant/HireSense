from __future__ import annotations

import uuid
from typing import Any

from hiresense.profile.domain.models import CandidateProfile


class InMemoryProfileRepository:
    """Process-local `ProfileRepositoryPort` for setups with no database.

    This is the null-object counterpart to `ProfileRepository`. It exists so
    `ProfileService` can depend on one non-optional repository instead of
    carrying an `if self._repository is not None: ... else: <dict>` fork through
    every method — the storage fallback belongs behind the port, not inside the
    service.

    It deliberately mirrors the SQL repository's *observable contract* rather
    than being a bare dict:

    * `list_all()` returns rows **newest-first**, matching the SQL repository's
      `ORDER BY created_at DESC`. Insertion order is treated as creation order.
    * `get_latest()` returns the most recently created row, optionally filtered
      by language.
    * `update()` / `update_all()` re-validate the row, the way the SQL
      repository writes columns and re-reads them through `_to_domain` — so a
      raw `apply_profile` dict comes back out as an `ApplyProfile`, not a dict.
    * Updates replace the stored model (`model_validate` produces a new object)
      instead of mutating the caller's instance.
    """

    def __init__(self) -> None:
        # Insertion order is creation order (oldest first). Reads that promise
        # "newest first" reverse it explicitly.
        self._rows: dict[str, CandidateProfile] = {}

    def get_by_id(self, id: uuid.UUID) -> CandidateProfile | None:
        return self._rows.get(str(id))

    def get_latest(self, language: str | None = None) -> CandidateProfile | None:
        rows = list(self._rows.values())
        if language:
            rows = [row for row in rows if row.language == language]
        return rows[-1] if rows else None

    def list_all(self) -> list[CandidateProfile]:
        return list(reversed(self._rows.values()))

    def create(
        self, profile: CandidateProfile, *, original_filename: str | None = None
    ) -> CandidateProfile:
        # `original_filename` is a write-only column on the SQL side (it is not
        # mapped back onto CandidateProfile), so there is nothing to retain here.
        self._rows[str(profile.id)] = profile
        return profile

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> CandidateProfile | None:
        key = str(id)
        row = self._rows.get(key)
        if row is None:
            return None
        updated = self._with_fields(row, fields)
        self._rows[key] = updated
        return updated

    def update_all(self, fields: dict[str, Any]) -> int:
        """Set the given fields on every stored profile, returning the row count.

        Mirrors `ProfileRepository.update_all`: an empty `fields` touches
        nothing and reports 0 rows.
        """
        if not fields:
            return 0
        for key, row in list(self._rows.items()):
            self._rows[key] = self._with_fields(row, fields)
        return len(self._rows)

    @staticmethod
    def _with_fields(row: CandidateProfile, fields: dict[str, Any]) -> CandidateProfile:
        """Return a copy of `row` with `fields` applied and re-validated.

        The SQL repository sets columns and re-reads the row through
        `_to_domain`, which turns the stored `apply_profile` JSON back into an
        `ApplyProfile`. Re-validating here keeps the field types identical
        across both repositories instead of leaving a raw dict on the model.
        Unknown keys are dropped, matching the SQL repository's `hasattr` guard.
        """
        known = {
            key: value for key, value in fields.items() if key in CandidateProfile.model_fields
        }
        if not known:
            return row
        return CandidateProfile.model_validate({**row.model_dump(), **known})
