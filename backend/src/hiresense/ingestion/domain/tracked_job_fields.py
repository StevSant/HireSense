from __future__ import annotations

from typing import Any

# Fields whose before-and-after values are worth storing verbatim. Kept
# deliberately small: these are the ones a human reads on a timeline
# ("salary changed, was blank, now $180-200K"). Fields already excluded from
# content_hash (identity, timestamps, scores) are not content changes and are
# absent here by construction.
TRACKED_FIELDS: tuple[str, ...] = (
    "title",
    "company",
    "salary_range",
    "location",
    "employment_type",
)

# Tracked as a changed/unchanged flag only. Descriptions are large and churn on
# whitespace and boilerplate; storing them before-and-after would dominate the
# table for little analytical value.
_FLAGGED_FIELDS: tuple[str, ...] = ("description",)


def diff_job_fields(old: Any, new: Any) -> dict[str, Any]:
    """Compare two jobs field by field, returning only what actually differed.

    Duck-typed on purpose: `old` is a SQLAlchemy row and `new` a NormalizedJob,
    and this module must not import either. Only getattr is used.
    """
    diff: dict[str, Any] = {}
    for field in TRACKED_FIELDS:
        old_value = getattr(old, field, None)
        new_value = getattr(new, field, None)
        if old_value != new_value:
            diff[field] = {"old": old_value, "new": new_value}
    for field in _FLAGGED_FIELDS:
        if getattr(old, field, None) != getattr(new, field, None):
            diff[field] = {"changed": True}
    return diff
