from __future__ import annotations

from pydantic import BaseModel


class FieldFill(BaseModel):
    """One autofill instruction for an ATS application form.

    `canonical_key` is the Apply Assist field name (see build_prefill); `value`
    is what to enter; `label_patterns` are lowercase substrings a client matches
    against the form's visible field labels to locate the right input.
    """

    canonical_key: str
    value: str | bool | int
    label_patterns: list[str]
