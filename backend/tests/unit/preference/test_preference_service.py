import uuid
from datetime import datetime, timezone

import pytest

from hiresense.preference.domain import (
    FeedbackKind,
    FeedbackSignal,
    FeedbackSource,
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


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list = []

    async def complete(self, prompt: str, system: str) -> str:
        self.calls.append((prompt, system))
        return self._text


class _FakeJobLookup:
    def __init__(self, titles: dict) -> None:
        self._titles = titles

    def get_job_by_id(self, job_id: str):
        title = self._titles.get(job_id)
        if title is None:
            return None
        return type("J", (), {"title": title, "company": "Acme"})()


class _RaisingLLM:
    async def complete(self, prompt: str, system: str) -> str:
        raise RuntimeError("llm down")


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
async def test_record_implicit_signal_sets_source_implicit() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    signal = await svc.record_implicit_signal(jid, FeedbackKind.OFFERED)
    assert signal.source == FeedbackSource.IMPLICIT
    assert signal.kind == FeedbackKind.OFFERED
    assert any(s.source == FeedbackSource.IMPLICIT for s in repo.list_signals())


@pytest.mark.asyncio
async def test_record_signal_still_explicit() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    signal = await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    assert signal.source == FeedbackSource.EXPLICIT


@pytest.mark.asyncio
async def test_reset_clears_signals_and_model() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    svc.reset()
    assert repo.cleared is True
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]


def _service_with_explainer(
    repo, vectors, *, llm=None, explanation_enabled: bool = False
) -> PreferenceService:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    return PreferenceService(
        repository=repo,
        vector_store=FakeVectorStore(vectors),
        calculator=calc,
        weights={k: 1.0 for k in FeedbackKind},
        enabled=True,
        llm=llm,
        explanation_enabled=explanation_enabled,
    )


@pytest.mark.asyncio
async def test_explain_summary_none_when_no_llm() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    exp = await svc.explain()
    assert exp.summary is None
    assert exp.total_signals == 1


@pytest.mark.asyncio
async def test_explain_layers_llm_summary() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    llm = _FakeLLM("You prefer backend roles.")
    svc = _service_with_explainer(
        repo, {str(jid): [0.0, 1.0]}, llm=llm, explanation_enabled=True
    )
    svc.attach_explainer(
        llm=llm, job_lookup=_FakeJobLookup({str(jid): "Backend Engineer"})
    )
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    exp = await svc.explain()
    assert exp.summary == "You prefer backend roles."
    assert len(llm.calls) == 1
    assert exp.total_signals == 1


@pytest.mark.asyncio
async def test_explain_summary_none_when_llm_raises() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service_with_explainer(
        repo, {str(jid): [0.0, 1.0]}, llm=_RaisingLLM(), explanation_enabled=True
    )
    svc.attach_explainer(
        llm=_RaisingLLM(), job_lookup=_FakeJobLookup({str(jid): "Backend Engineer"})
    )
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    exp = await svc.explain()
    assert exp.summary is None
    assert exp.total_signals == 1
