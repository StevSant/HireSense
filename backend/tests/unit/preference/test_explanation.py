import uuid

from hiresense.preference.domain import FeedbackKind, FeedbackSignal, FeedbackSource
from hiresense.preference.domain.explanation import build_explanation


def _sig(kind: FeedbackKind, emb=None) -> FeedbackSignal:
    return FeedbackSignal(
        id=uuid.uuid4(), job_id=uuid.uuid4(), kind=kind,
        source=FeedbackSource.EXPLICIT, job_embedding=emb,
    )


def test_empty_signals_report_inactive() -> None:
    exp = build_explanation([], delta_vector=None)
    assert exp.active is False
    assert exp.total_signals == 0
    assert exp.drift_magnitude == 0.0


def test_counts_by_kind_and_polarity() -> None:
    signals = [
        _sig(FeedbackKind.THUMBS_UP),
        _sig(FeedbackKind.THUMBS_UP),
        _sig(FeedbackKind.NOT_INTERESTED),
    ]
    exp = build_explanation(signals, delta_vector=[0.0, 0.0])
    assert exp.total_signals == 3
    assert exp.positive_count == 2
    assert exp.negative_count == 1
    assert exp.counts_by_kind["thumbs_up"] == 2


def test_drift_magnitude_is_delta_norm() -> None:
    exp = build_explanation([_sig(FeedbackKind.THUMBS_UP)], delta_vector=[3.0, 4.0])
    assert exp.active is True
    assert abs(exp.drift_magnitude - 5.0) < 1e-9
