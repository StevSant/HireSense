from hiresense.preference.domain import FeedbackKind, FeedbackSource


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
