import uuid
from datetime import datetime, timezone

from hiresense.preference.domain import (
    FeedbackKind,
    FeedbackSignal,
    FeedbackSource,
    PreferenceModel,
    SignalContribution,
)


def test_explicit_kinds_exist() -> None:
    assert FeedbackKind.THUMBS_UP == "thumbs_up"
    assert FeedbackKind.THUMBS_DOWN == "thumbs_down"
    assert FeedbackKind.NOT_INTERESTED == "not_interested"
    assert FeedbackKind.MORE_LIKE_THIS == "more_like_this"


def test_polarity_is_plus_one_for_positive_kinds() -> None:
    assert FeedbackKind.THUMBS_UP.polarity == 1
    assert FeedbackKind.MORE_LIKE_THIS.polarity == 1


def test_polarity_is_minus_one_for_negative_kinds() -> None:
    assert FeedbackKind.THUMBS_DOWN.polarity == -1
    assert FeedbackKind.NOT_INTERESTED.polarity == -1


def test_weight_key_maps_to_settings_attribute() -> None:
    assert FeedbackKind.THUMBS_UP.weight_key == "preference_weight_thumbs_up"
    assert FeedbackKind.NOT_INTERESTED.weight_key == "preference_weight_not_interested"


def test_source_values() -> None:
    assert FeedbackSource.EXPLICIT == "explicit"
    assert FeedbackSource.IMPLICIT == "implicit"


def test_feedback_signal_defaults() -> None:
    sig = FeedbackSignal(
        job_id=uuid.uuid4(),
        kind=FeedbackKind.THUMBS_UP,
        source=FeedbackSource.EXPLICIT,
    )
    assert sig.id is None
    assert sig.job_embedding is None
    assert sig.created_at is None


def test_feedback_signal_holds_embedding() -> None:
    sig = FeedbackSignal(
        job_id=uuid.uuid4(),
        kind=FeedbackKind.NOT_INTERESTED,
        source=FeedbackSource.EXPLICIT,
        job_embedding=[0.1, 0.2, 0.3],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert sig.job_embedding == [0.1, 0.2, 0.3]


def test_preference_model_defaults() -> None:
    model = PreferenceModel(delta_vector=[0.0, 0.0])
    assert model.version == 1
    assert model.delta_vector == [0.0, 0.0]


def test_signal_contribution_fields() -> None:
    c = SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=2.0, age_days=10.0)
    assert c.polarity == 1
    assert c.age_days == 10.0


def test_implicit_kinds_exist_and_have_expected_polarity():
    assert FeedbackKind.APPLIED.value == "applied"
    assert FeedbackKind.INTERVIEWING.value == "interviewing"
    assert FeedbackKind.OFFERED.value == "offered"
    assert FeedbackKind.ACCEPTED.value == "accepted"
    assert FeedbackKind.REJECTED.value == "rejected"
    assert FeedbackKind.APPLIED.polarity == 1
    assert FeedbackKind.INTERVIEWING.polarity == 1
    assert FeedbackKind.OFFERED.polarity == 1
    assert FeedbackKind.ACCEPTED.polarity == 1
    assert FeedbackKind.REJECTED.polarity == -1


def test_implicit_kinds_weight_keys():
    assert FeedbackKind.OFFERED.weight_key == "preference_weight_offered"
    assert FeedbackKind.REJECTED.weight_key == "preference_weight_rejected"
