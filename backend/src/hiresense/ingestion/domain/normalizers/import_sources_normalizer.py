from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers._import_fields import (
    as_string_list,
    build_salary_range,
    clean_description,
    first_bool,
    first_str,
    normalize_employment_type,
    normalize_remote_modality,
    parse_posted_date,
)


def _base_import_normalize(d: dict[str, Any]) -> dict[str, Any]:
    location = first_str(d, "location", "job_location")
    remote_modality = normalize_remote_modality(
        explicit=first_str(d, "remote_modality", "workplace", "work_type") or None,
        remote_flag=first_bool(d, "remote", "is_remote", "remote_ok"),
        location=location,
    )
    salary_range, salary_meta = build_salary_range(d)
    equity = first_str(d, "equity_range", "equity") or None
    employment = normalize_employment_type(d.get("employment_type") or d.get("job_type"))
    skills = as_string_list(d.get("skills") or d.get("technologies") or d.get("tags") or [])
    url = first_str(d, "url", "link", "job_url", "canonical_url")
    apply_url = first_str(d, "apply_url", "application_url", "applyUrl")
    meta: dict[str, Any] = dict(salary_meta)
    if apply_url:
        meta["application_url"] = apply_url
    for key in (
        "easy_apply",
        "company_stage",
        "team_size",
        "funding",
        "industry",
        "company_rating",
        "company_size",
        "headquarters",
        "contract_duration",
        "employer_type",
        "experience_level",
        "geographic_restrictions",
        "yc_batch",
    ):
        if d.get(key) is not None and d.get(key) != "":
            meta[key] = d[key]
    if first_bool(d, "easy_apply", "easyApply") is not None:
        meta["easy_apply"] = first_bool(d, "easy_apply", "easyApply")
    countries = as_string_list(d.get("countries") or d.get("geographic_restrictions") or [])
    visa = first_bool(d, "visa_sponsorship_available", "visa_sponsorship", "sponsors_visa")
    return {
        "title": first_str(d, "title", "job_title"),
        "company": first_str(d, "company", "company_name"),
        "description": clean_description(d.get("description") or d.get("summary") or ""),
        "skills": skills,
        "location": location,
        "salary_range": salary_range,
        "employment_type": employment,
        "equity_range": equity,
        "url": url,
        "language": first_str(d, "language") or "en",
        "posted_date": parse_posted_date(
            d.get("posted_date") or d.get("published") or d.get("date")
        ),
        "remote_modality": remote_modality,
        "visa_sponsorship_available": visa,
        "countries": countries,
        "source_metadata": meta,
    }


class IndeedNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        data = _base_import_normalize(raw.raw_data)
        data["source_metadata"] = {
            **data.get("source_metadata", {}),
            "platform": "indeed",
        }
        return data


class WellfoundNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        data = _base_import_normalize(d)
        meta = dict(data.get("source_metadata") or {})
        meta["platform"] = "wellfound"
        for key, out in (
            ("stage", "company_stage"),
            ("company_stage", "company_stage"),
            ("team_size", "team_size"),
            ("funding", "funding"),
            ("total_raised", "funding"),
            ("industry", "industry"),
            ("geographic_restrictions", "geographic_restrictions"),
        ):
            if d.get(key) is not None and out not in meta:
                meta[out] = d[key]
        data["source_metadata"] = meta
        return data


class GlassdoorNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        data = _base_import_normalize(d)
        meta = dict(data.get("source_metadata") or {})
        meta["platform"] = "glassdoor"
        for key in ("company_rating", "company_size", "industry", "headquarters"):
            if d.get(key) is not None:
                meta[key] = d[key]
        # Explicitly refuse review payloads if present — do not persist.
        meta.pop("reviews", None)
        meta.pop("review_text", None)
        data["source_metadata"] = meta
        return data


class MonsterNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        data = _base_import_normalize(raw.raw_data)
        data["source_metadata"] = {
            **data.get("source_metadata", {}),
            "platform": "monster",
        }
        return data
