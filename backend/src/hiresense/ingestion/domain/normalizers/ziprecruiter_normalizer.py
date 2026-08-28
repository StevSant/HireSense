from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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


def _strip_tracking(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith(("utm_", "trk_"))
    ]
    return urlunparse(parsed._replace(query=urlencode(query)))


class ZipRecruiterNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        location_value = d.get("location")
        if isinstance(location_value, dict):
            location = first_str(location_value, "display_name", "displayName", "name", "city")
        else:
            location = str(location_value or "").strip()

        workplace = first_str(
            d, "workplace_type", "workplaceType", "work_arrangement", "workArrangement"
        )
        remote_modality = normalize_remote_modality(
            explicit=workplace,
            remote_flag=first_bool(d, "is_remote", "isRemote", "remote", "accept_remote"),
            location=location,
        )
        if remote_modality == "remote" and location and "remote" not in location.lower():
            location = f"{location} (Remote)"

        salary_data = dict(d)
        for source_key, target_key in (
            ("salary_min_annual", "salary_min"),
            ("salary_max_annual", "salary_max"),
            ("compensation_min", "salary_min"),
            ("compensation_max", "salary_max"),
            ("compensation_currency", "currency"),
            ("compensation_period", "period"),
        ):
            if salary_data.get(target_key) is None and salary_data.get(source_key) is not None:
                salary_data[target_key] = salary_data[source_key]
        salary, salary_meta = build_salary_range(
            salary_data,
            range_keys=("salary", "salary_range", "salaryRange", "compensation"),
        )
        skills = as_string_list(d.get("skills") or d.get("technologies") or d.get("tags"))
        url = _strip_tracking(
            first_str(d, "url", "job_url", "jobUrl", "details_url", "detailsUrl", "listing_url")
        )
        apply_url = _strip_tracking(first_str(d, "apply_url", "applyUrl", "application_url"))

        metadata: dict[str, Any] = dict(salary_meta)
        for key, output_key in (
            ("company_url", "company_url"),
            ("companyUrl", "company_url"),
            ("employer_url", "company_url"),
            ("employerUrl", "company_url"),
            ("easy_apply", "easy_apply"),
            ("easyApply", "easy_apply"),
        ):
            if d.get(key) is not None and output_key not in metadata:
                metadata[output_key] = d[key]
        if apply_url:
            metadata["application_url"] = apply_url

        country = first_str(d, "country", "country_code", "countryCode")
        countries = [country] if country else []
        return {
            "title": first_str(d, "title", "job_title", "jobTitle"),
            "company": first_str(
                d, "company", "company_name", "companyName", "employer", "employer_name"
            ),
            "description": clean_description(
                d.get("description")
                or d.get("full_description")
                or d.get("fullDescription")
                or d.get("summary")
                or d.get("snippet")
                or ""
            ),
            "skills": skills,
            "location": location,
            "salary_range": salary,
            "employment_type": normalize_employment_type(
                d.get("employment_type") or d.get("employmentType") or d.get("job_type")
            ),
            "equity_range": None,
            "url": url,
            "language": "en",
            "posted_date": parse_posted_date(
                d.get("posted_date")
                or d.get("postedDate")
                or d.get("date_posted")
                or d.get("datePosted")
                or d.get("posted_at")
            ),
            "remote_modality": remote_modality,
            "countries": countries,
            "source_metadata": metadata,
        }
