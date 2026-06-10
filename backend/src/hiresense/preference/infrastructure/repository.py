from __future__ import annotations

from sqlalchemy import delete, select

from hiresense.infrastructure import SqlRepository
from hiresense.preference.domain import FeedbackSignal, PreferenceModel
from hiresense.preference.infrastructure.orm import FeedbackSignalOrm, PreferenceModelOrm

_MODEL_ID = 1


class PreferenceRepository(SqlRepository):
    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal:
        row = FeedbackSignalOrm(
            job_id=signal.job_id,
            kind=signal.kind.value,
            source=signal.source.value,
            job_embedding=signal.job_embedding,
            dimension_scores=signal.dimension_scores,
        )
        return self._insert(row, FeedbackSignal.model_validate)

    def list_signals(self) -> list[FeedbackSignal]:
        return self._select_all(select(FeedbackSignalOrm), FeedbackSignal.model_validate)

    def get_model(self) -> PreferenceModel | None:
        return self._get_by_pk(PreferenceModelOrm, _MODEL_ID, self._to_domain)

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
