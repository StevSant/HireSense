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
    WeightNudgeCalculator,
)


class FakeRepo:
    def __init__(self) -> None:
        self.signals: list[FeedbackSignal] = []
        self.model: PreferenceModel | None = None
        self.cleared = False

    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal:
        signal = signal.model_copy(
            update={"id": uuid.uuid4(), "created_at": datetime.now(timezone.utc)}
        )
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
    svc = _service_with_explainer(repo, {str(jid): [0.0, 1.0]}, llm=llm, explanation_enabled=True)
    svc.attach_job_lookup(_FakeJobLookup({str(jid): "Backend Engineer"}))
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    exp = await svc.explain()
    assert exp.summary == "You prefer backend roles."
    assert len(llm.calls) == 1
    assert exp.total_signals == 1


class _FakeDimScorer:
    """Async scorer that returns fixed dimension scores for any job id."""

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores
        self.calls: list[str] = []

    async def score_dimensions(self, job_id: str) -> dict[str, float] | None:
        self.calls.append(job_id)
        return dict(self._scores)


class _NoneDimScorer:
    """Scorer that always returns None (job/profile/LLM unavailable)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def score_dimensions(self, job_id: str) -> dict[str, float] | None:
        self.calls.append(job_id)
        return None


class _RaisingDimScorer:
    """Scorer that raises — capture must degrade gracefully."""

    async def score_dimensions(self, job_id: str) -> dict[str, float] | None:  # noqa: ARG002
        raise RuntimeError("scorer down")


def _service_with_nudge(
    repo, vectors, *, min_outcomes=3, clamp=3, scale=10.0, base_weights=None
) -> PreferenceService:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    nudge = WeightNudgeCalculator(min_outcomes=min_outcomes, clamp=clamp, scale=scale)
    return PreferenceService(
        repository=repo,
        vector_store=FakeVectorStore(vectors),
        calculator=calc,
        weights={k: 1.0 for k in FeedbackKind},
        enabled=True,
        nudge_calculator=nudge,
        base_weights=base_weights or {},
    )


@pytest.mark.asyncio
async def test_weight_overrides_empty_without_dimension_scorer() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service_with_nudge(repo, {str(jid): [0.0, 1.0]}, min_outcomes=1)
    # No dimension scorer attached -> signal carries no scores -> no overrides.
    await svc.record_implicit_signal(jid, FeedbackKind.OFFERED)
    assert svc.weight_overrides() == {}


@pytest.mark.asyncio
async def test_implicit_signal_captures_dimensions_at_record_time() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    scorer = _FakeDimScorer({"comp": 1.0})
    svc = _service_with_nudge(repo, {}, min_outcomes=1)
    svc.attach_dimension_scorer(scorer)
    await svc.record_implicit_signal(jid, FeedbackKind.OFFERED)
    # The scorer was called for the job id and the scores were snapshotted.
    assert scorer.calls == [str(jid)]
    assert repo.signals[0].dimension_scores == {"comp": 1.0}


@pytest.mark.asyncio
async def test_explicit_signal_does_not_capture_dimensions() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    scorer = _FakeDimScorer({"comp": 1.0})
    svc = _service_with_nudge(repo, {}, min_outcomes=1)
    svc.attach_dimension_scorer(scorer)
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    # Explicit thumbs signals never trigger dimension capture.
    assert scorer.calls == []
    assert repo.signals[0].dimension_scores is None


@pytest.mark.asyncio
async def test_capture_returns_none_stores_signal_without_scores() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service_with_nudge(repo, {}, min_outcomes=1)
    svc.attach_dimension_scorer(_NoneDimScorer())
    await svc.record_implicit_signal(jid, FeedbackKind.OFFERED)
    assert repo.signals[0].dimension_scores is None
    assert svc.weight_overrides() == {}


@pytest.mark.asyncio
async def test_capture_raises_degrades_gracefully() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service_with_nudge(repo, {}, min_outcomes=1)
    svc.attach_dimension_scorer(_RaisingDimScorer())
    # No crash; signal still stored, just without dimension scores.
    signal = await svc.record_implicit_signal(jid, FeedbackKind.OFFERED)
    assert signal.dimension_scores is None
    assert repo.signals[0].dimension_scores is None
    assert svc.weight_overrides() == {}


@pytest.mark.asyncio
async def test_weight_overrides_gated_below_min_outcomes() -> None:
    repo = FakeRepo()
    svc = _service_with_nudge(repo, {}, min_outcomes=5)
    svc.attach_dimension_scorer(_FakeDimScorer({"comp": 1.0}))
    for _ in range(3):
        await svc.record_implicit_signal(uuid.uuid4(), FeedbackKind.OFFERED)
    assert svc.weight_overrides() == {}


@pytest.mark.asyncio
async def test_weight_overrides_computed_once_gate_met() -> None:
    repo = FakeRepo()
    svc = _service_with_nudge(repo, {}, min_outcomes=3, clamp=3, scale=10.0)
    svc.attach_dimension_scorer(_FakeDimScorer({"comp": 1.0}))
    for _ in range(3):
        await svc.record_implicit_signal(uuid.uuid4(), FeedbackKind.OFFERED)
    overrides = svc.weight_overrides()
    assert overrides.get("comp", 0) > 0


@pytest.mark.asyncio
async def test_compute_overrides_ignores_signals_without_scores() -> None:
    # Signals captured before a scorer was attached carry no scores and must
    # not contribute; only the score-bearing signals count toward the gate.
    repo = FakeRepo()
    svc = _service_with_nudge(repo, {}, min_outcomes=3, clamp=3, scale=10.0)
    # Two outcomes without a scorer -> no scores.
    for _ in range(2):
        await svc.record_implicit_signal(uuid.uuid4(), FeedbackKind.OFFERED)
    assert svc.weight_overrides() == {}
    # Attach a scorer and add three more -> only those three meet the gate.
    svc.attach_dimension_scorer(_FakeDimScorer({"comp": 1.0}))
    for _ in range(3):
        await svc.record_implicit_signal(uuid.uuid4(), FeedbackKind.OFFERED)
    assert svc.weight_overrides().get("comp", 0) > 0


@pytest.mark.asyncio
async def test_weight_overrides_empty_when_disabled() -> None:
    repo = FakeRepo()
    svc = _service_with_nudge(repo, {}, min_outcomes=1)
    svc.attach_dimension_scorer(_FakeDimScorer({"comp": 1.0}))
    svc._enabled = False  # disabled service exposes no overrides
    await svc.record_implicit_signal(uuid.uuid4(), FeedbackKind.OFFERED)
    assert svc.weight_overrides() == {}


@pytest.mark.asyncio
async def test_explain_includes_weight_overrides() -> None:
    repo = FakeRepo()
    svc = _service_with_nudge(repo, {}, min_outcomes=3, clamp=3, scale=10.0)
    svc.attach_dimension_scorer(_FakeDimScorer({"comp": 1.0}))
    for _ in range(3):
        await svc.record_implicit_signal(uuid.uuid4(), FeedbackKind.OFFERED)
    exp = await svc.explain()
    assert exp.weight_overrides.get("comp", 0) > 0


@pytest.mark.asyncio
async def test_reset_clears_weight_overrides() -> None:
    repo = FakeRepo()
    svc = _service_with_nudge(repo, {}, min_outcomes=3, clamp=3, scale=10.0)
    svc.attach_dimension_scorer(_FakeDimScorer({"comp": 1.0}))
    for _ in range(3):
        await svc.record_implicit_signal(uuid.uuid4(), FeedbackKind.OFFERED)
    assert svc.weight_overrides() != {}
    svc.reset()
    assert svc.weight_overrides() == {}


def test_weights_view_reports_base_override_effective() -> None:
    repo = FakeRepo()
    svc = _service_with_nudge(repo, {}, base_weights={"comp": 10, "culture": 5})
    # Inject a model with an override directly via the repo.
    repo.save_model(PreferenceModel(delta_vector=[], weight_overrides={"comp": 2}))
    view = {row["dimension"]: row for row in svc.weights_view()}
    assert view["comp"]["base_weight"] == 10
    assert view["comp"]["override"] == 2
    assert view["comp"]["effective_weight"] == 12
    assert view["culture"]["base_weight"] == 5
    assert view["culture"]["override"] == 0
    assert view["culture"]["effective_weight"] == 5


@pytest.mark.asyncio
async def test_explain_summary_none_when_llm_raises() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service_with_explainer(
        repo, {str(jid): [0.0, 1.0]}, llm=_RaisingLLM(), explanation_enabled=True
    )
    svc.attach_job_lookup(_FakeJobLookup({str(jid): "Backend Engineer"}))
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    exp = await svc.explain()
    assert exp.summary is None
    assert exp.total_signals == 1
