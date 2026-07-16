from __future__ import annotations

import asyncio

import pytest

from hiresense.admin.domain.usage_recorder import UsageRecorder


class _FakeInstrument:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict]] = []

    def add(self, value, attributes=None) -> None:
        self.calls.append((value, attributes or {}))

    def record(self, value, attributes=None) -> None:
        self.calls.append((value, attributes or {}))


class _FakeDomainMetrics:
    def __init__(self) -> None:
        self.llm_tokens_total = _FakeInstrument()
        self.llm_cost_usd_total = _FakeInstrument()
        self.llm_call_duration_ms = _FakeInstrument()
        self.llm_errors_total = _FakeInstrument()


class _FakeRepo:
    def __init__(self) -> None:
        self.inserted: list[dict] = []

    def insert(self, **kwargs) -> None:
        self.inserted.append(kwargs)

    def totals(self, since=None):  # pragma: no cover - not exercised here
        raise NotImplementedError


def _record_kwargs(feature_key: str = "cv_parser") -> dict:
    return dict(
        feature_key=feature_key,
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        cost_usd=0.001,
        latency_ms=42.0,
        success=True,
        error=None,
        user_id=None,
    )


def test_record_tags_tokens_and_duration_with_feature_label(monkeypatch) -> None:
    fake_metrics = _FakeDomainMetrics()
    monkeypatch.setattr(
        "hiresense.admin.domain.usage_recorder.get_domain_metrics",
        lambda: fake_metrics,
    )
    recorder = UsageRecorder(_FakeRepo())

    recorder.record(**_record_kwargs(feature_key="cv_parser"))

    assert all(attrs.get("feature") == "cv_parser" for _, attrs in fake_metrics.llm_tokens_total.calls)
    assert all(
        attrs.get("feature") == "cv_parser" for _, attrs in fake_metrics.llm_call_duration_ms.calls
    )


@pytest.mark.asyncio
async def test_record_retains_task_ref_until_persisted(monkeypatch) -> None:
    # Without retaining a reference, an unawaited create_task() result can be
    # garbage-collected before it runs, silently dropping the DB write. This
    # asserts the task is tracked while pending and discarded once done.
    fake_metrics = _FakeDomainMetrics()
    monkeypatch.setattr(
        "hiresense.admin.domain.usage_recorder.get_domain_metrics",
        lambda: fake_metrics,
    )
    repo = _FakeRepo()
    recorder = UsageRecorder(repo)

    recorder.record(**_record_kwargs())

    assert len(recorder._background_tasks) == 1
    (pending_task,) = tuple(recorder._background_tasks)

    await pending_task  # drain

    assert recorder._background_tasks == set()
    assert len(repo.inserted) == 1
    assert repo.inserted[0]["feature_key"] == "cv_parser"


@pytest.mark.asyncio
async def test_record_handles_concurrent_bursts() -> None:
    repo = _FakeRepo()
    recorder = UsageRecorder(repo)

    for i in range(5):
        recorder.record(**_record_kwargs(feature_key=f"feature-{i}"))

    assert len(recorder._background_tasks) == 5
    await asyncio.gather(*recorder._background_tasks)

    assert recorder._background_tasks == set()
    assert len(repo.inserted) == 5
