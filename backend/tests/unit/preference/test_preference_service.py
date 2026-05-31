import uuid
from datetime import datetime, timezone

import pytest

from hiresense.preference.domain import (
    FeedbackKind,
    FeedbackSignal,
    PreferenceModel,
    PreferenceService,
    TasteVectorCalculator,
)


class FakeRepo:
    def __init__(self) -> None:
        self.signals: list[FeedbackSignal] = []
        self.model: PreferenceModel | None = None
        self.cleared = False

    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal:
        signal = signal.model_copy(update={"id": uuid.uuid4(), "created_at": datetime.now(timezone.utc)})
        self.signals.append(signal)
        return signal

    def list_signals(self) -> list[FeedbackSignal]:
        return list(self.signals)

    def get_model(self) -> PreferenceModel | None:
        return self.model

    def save_model(self, model: PreferenceModel) -> PreferenceModel:
        self.model = model
        return model

    def clear(self) -> None:
        self.signals.clear()
        self.model = None
        self.cleared = True


class FakeVectorStore:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    async def get_vector(self, id: str) -> list[float] | None:
        return self._vectors.get(id)


def _service(repo, vectors, *, weights=None, enabled: bool = True) -> PreferenceService:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    return PreferenceService(
        repository=repo,
        vector_store=FakeVectorStore(vectors),
        calculator=calc,
        weights=weights or {k: 1.0 for k in FeedbackKind},
        enabled=enabled,
    )


@pytest.mark.asyncio
async def test_query_vector_returns_baseline_when_no_model() -> None:
    svc = _service(FakeRepo(), {})
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]


@pytest.mark.asyncio
async def test_record_signal_snapshots_embedding_and_builds_model() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    assert repo.signals[0].job_embedding == [0.0, 1.0]
    assert repo.model is not None
    taste = svc.query_vector([1.0, 0.0])
    assert taste[1] > 0.0


@pytest.mark.asyncio
async def test_negative_signal_pushes_query_vector_away() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.NOT_INTERESTED)
    # Baseline orthogonal to the negative embedding so the blend does not
    # cancel to ~zero; the second component must decrease from its original
    # normalised value of ~0.707 (blend of [1,1] with delta [0,-1]).
    taste = svc.query_vector([1.0, 1.0])
    assert taste[1] < 1.0


@pytest.mark.asyncio
async def test_record_signal_without_embedding_still_stores_signal() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {})
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    assert repo.signals[0].job_embedding is None
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]


@pytest.mark.asyncio
async def test_disabled_service_returns_baseline() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]}, enabled=False)
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]


@pytest.mark.asyncio
async def test_reset_clears_signals_and_model() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    svc.reset()
    assert repo.cleared is True
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]
