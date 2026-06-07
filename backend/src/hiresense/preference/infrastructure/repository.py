from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from hiresense.preference.domain import FeedbackSignal, PreferenceModel
from hiresense.preference.infrastructure.orm import FeedbackSignalOrm, PreferenceModelOrm

_MODEL_ID = 1


class PreferenceRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal:
        with self._session_factory() as session:
            row = FeedbackSignalOrm(
                job_id=signal.job_id,
                kind=signal.kind.value,
                source=signal.source.value,
                job_embedding=signal.job_embedding,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return FeedbackSignal.model_validate(row)

    def list_signals(self) -> list[FeedbackSignal]:
        with self._session_factory() as session:
            rows = session.scalars(select(FeedbackSignalOrm)).all()
            return [FeedbackSignal.model_validate(r) for r in rows]

    def get_model(self) -> PreferenceModel | None:
        with self._session_factory() as session:
            row = session.get(PreferenceModelOrm, _MODEL_ID)
            return self._to_domain(row) if row is not None else None

    def save_model(self, model: PreferenceModel) -> PreferenceModel:
        with self._session_factory() as session:
            row = session.get(PreferenceModelOrm, _MODEL_ID)
            if row is None:
                row = PreferenceModelOrm(
                    id=_MODEL_ID,
                    delta_vector=model.delta_vector,
                    weight_overrides=dict(model.weight_overrides),
                    version=model.version,
                )
                session.add(row)
            else:
                row.delta_vector = model.delta_vector
                row.weight_overrides = dict(model.weight_overrides)
                row.version = model.version
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    @staticmethod
    def _to_domain(row: PreferenceModelOrm) -> PreferenceModel:
        # A pre-Phase-2 row (or any NULL column) reads back as no overrides.
        return PreferenceModel(
            delta_vector=row.delta_vector,
            weight_overrides=row.weight_overrides or {},
            version=row.version,
            updated_at=row.updated_at,
        )

    def clear(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(FeedbackSignalOrm))
            session.execute(delete(PreferenceModelOrm))
            session.commit()
