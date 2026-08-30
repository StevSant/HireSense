from __future__ import annotations

import re
from typing import Any

from hiresense.submission.domain.answer_source import AnswerSource
from hiresense.submission.domain.field_answer import FieldAnswer

# An answer longer than this is not a screening response, it is a runaway
# generation. Forms that genuinely want an essay still fit comfortably.
MAX_ANSWER_CHARS = 2000

# Answers whose source is the candidate's own data, copied verbatim. These are
# not generated, so there is nothing to hallucinate and nothing to validate.
_TRUSTED_SOURCES = frozenset({AnswerSource.DETERMINISTIC_MAP, AnswerSource.PROFILE})

_DIGITS = re.compile(r"\d")
_DATE_LIKE = re.compile(
    r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2})\b",
    re.IGNORECASE,
)
_BOOLEAN_LIKE = re.compile(r"^(yes|no|true|false|y|n)$", re.IGNORECASE)
_EMAIL_LIKE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.IGNORECASE)
_URL_LIKE = re.compile(r"https?://|www\.", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Canonical keys whose value is a fact about the candidate rather than prose.
# These are checked even when the value itself looks like ordinary text, because
# an invented credential or authorization status is exactly the failure mode
# this validator exists to prevent.
_FACTUAL_KEYS = frozenset(
    {
        "years_of_experience",
        "desired_salary",
        "start_availability",
        "requires_visa_sponsorship",
        "willing_to_relocate",
        "work_authorization",
        "email",
        "phone",
        "linkedin_url",
        "github_url",
        "portfolio_url",
    }
)

# Boolean words that mean the same thing, so "yes" grounds against True.
_TRUTHY = frozenset({"yes", "y", "true"})
_FALSY = frozenset({"no", "n", "false"})


def _normalize(value: Any) -> str:
    """Casefold and strip punctuation so values compare on their content."""
    return _NON_ALNUM.sub(" ", str(value).casefold()).strip()


def _is_factual(answer: FieldAnswer, value: str) -> bool:
    """True when the answer asserts a checkable fact rather than prose."""
    if answer.canonical_key in _FACTUAL_KEYS:
        return True
    if _BOOLEAN_LIKE.match(value.strip()):
        return True
    if _EMAIL_LIKE.search(value) or _URL_LIKE.search(value):
        return True
    if _DATE_LIKE.search(value):
        return True
    # A short value carrying digits is a number the model chose; a long prose
    # answer that happens to mention a year is not.
    return bool(_DIGITS.search(value)) and len(value) <= 120


def _boolean_haystack(prefill: dict[str, Any]) -> set[str]:
    """Render profile booleans as the words a form would use for them."""
    words: set[str] = set()
    for raw in prefill.values():
        if isinstance(raw, bool):
            words.update(_TRUTHY if raw else _FALSY)
    return words


def _is_grounded(value: str, haystack: str, boolean_words: set[str]) -> bool:
    normalized = _normalize(value)
    if not normalized:
        return False
    if normalized in boolean_words:
        return True
    return normalized in haystack


def enforce_grounding(
    answers: list[FieldAnswer],
    *,
    prefill: dict[str, Any],
    claim_texts: list[str],
    job_text: str,
) -> list[FieldAnswer]:
    """Demote any generated answer not traceable to the candidate's own data.

    This is the invariant that separates an auto-applier from a system that
    fabricates credentials under someone's name, and it is deliberately not
    configurable. A model may write prose freely, but every checkable fact it
    asserts -- a number, a date, a yes/no, a credential, a contact detail --
    must already appear in the candidate's profile, in a verified claim, or in
    the job posting itself. Anything else is forced to zero confidence, which
    the confidence gate then turns into an escalation to the human.

    Answers sourced from the deterministic label map or straight from the
    profile are returned untouched: they are copies, not assertions.
    """
    haystack = " ".join(
        [
            *(_normalize(v) for v in prefill.values()),
            *(_normalize(t) for t in claim_texts),
            _normalize(job_text),
        ]
    )
    boolean_words = _boolean_haystack(prefill)

    validated: list[FieldAnswer] = []
    for answer in answers:
        if answer.source in _TRUSTED_SOURCES:
            validated.append(answer)
            continue

        value = answer.value or ""
        reason: str | None = None
        if not value.strip():
            reason = "empty answer"
        elif len(value) > MAX_ANSWER_CHARS:
            reason = f"answer exceeds {MAX_ANSWER_CHARS} characters"
        elif _is_factual(answer, value) and not _is_grounded(value, haystack, boolean_words):
            reason = "value is not supported by the profile, a verified claim, or the job posting"

        if reason is None:
            validated.append(answer)
            continue

        validated.append(
            answer.model_copy(update={"confidence": 0.0, "rationale": f"ungrounded: {reason}"})
        )
    return validated
