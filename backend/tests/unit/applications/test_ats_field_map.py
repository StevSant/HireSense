from __future__ import annotations

import pytest

from hiresense.applications.domain import FieldFill, build_autofill_plan


@pytest.mark.parametrize("ats_type", [None, ""])
def test_non_ats_jobs_have_no_autofill_plan(ats_type) -> None:
    # Redirect / unknown jobs (Phase 0) aren't autofillable.
    assert build_autofill_plan(ats_type, {"email": "a@b.com"}) == []


def test_plan_maps_known_keys_with_label_patterns_and_preserves_value_types() -> None:
    prefill = {
        "first_name": "Ada",
        "email": "ada@example.com",
        "requires_visa_sponsorship": False,
        "years_of_experience": 8,
        "linkedin_url": "https://linkedin.com/in/ada",
    }

    plan = build_autofill_plan("greenhouse", prefill)
    by_key = {f.canonical_key: f for f in plan}

    assert set(by_key) == set(prefill)
    assert by_key["first_name"].label_patterns == ["first name"]
    assert "email" in by_key["email"].label_patterns
    # Non-string values survive as-is (the client formats per field type).
    assert by_key["requires_visa_sponsorship"].value is False
    assert by_key["years_of_experience"].value == 8
    assert all(isinstance(f, FieldFill) for f in plan)


def test_plan_ignores_keys_without_a_known_label_mapping() -> None:
    plan = build_autofill_plan("lever", {"email": "a@b.com", "unmapped_field": "x"})
    assert [f.canonical_key for f in plan] == ["email"]


def test_plan_order_is_stable() -> None:
    prefill = {"email": "a@b.com", "first_name": "Ada", "phone": "123"}
    plan = build_autofill_plan("ashby", prefill)
    # Stable label-map order, not insertion order of the prefill dict.
    assert [f.canonical_key for f in plan] == ["first_name", "email", "phone"]
