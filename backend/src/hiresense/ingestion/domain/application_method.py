from __future__ import annotations

import enum


class ApplicationMethod(str, enum.Enum):
    """How a candidate applies to a job, derived once at ingestion.

    ATS_FORM  — the URL is a direct applicant-tracking-system application form
                (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee).
                These are the jobs Apply Assist can prefill and hand off.
    REDIRECT  — the URL is an aggregator/landing page; applying happens somewhere
                downstream (Remotive, Adzuna, LinkedIn guest pages, etc.).
    UNKNOWN   — no URL is available, so the method can't be determined.
    """

    ATS_FORM = "ats_form"
    REDIRECT = "redirect"
    UNKNOWN = "unknown"
