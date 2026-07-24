from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers._import_fields import (
    as_string_list,
    clean_description,
    first_bool,
    first_str,
    normalize_employment_type,
    normalize_remote_modality,
    parse_posted_date,
)


def _strip_utm(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
    ]
    return urlunparse(parsed._replace(query=urlencode(query)))


class DiceNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        location_obj = d.get("jobLocation")
        location = ""
        if isinstance(location_obj, dict):
            location = first_str(location_obj, "displayName", "city", "region")
        elif isinstance(location_obj, str):
            location = location_obj
        location = location or first_str(d, "location")

        workplace = d.get("workplaceTypes") or []
        workplace_l = [str(w).lower() for w in workplace] if isinstance(workplace, list) else []
        explicit = None
        if "hybrid" in workplace_l:
            explicit = "hybrid"
        elif "remote" in workplace_l and not any(
            w in workplace_l for w in ("on-site", "onsite", "on_site")
        ):
            explicit = "remote"
        elif any(w in workplace_l for w in ("on-site", "onsite", "on_site")):
            explicit = "on_site"

        remote_modality = normalize_remote_modality(
            explicit=explicit,
            remote_flag=first_bool(d, "isRemote"),
            location=location,
        )
        if remote_modality == "remote" and location and "remote" not in location.lower():
            location = f"{location} (Remote)"

        salary = first_str(d, "salary") or None
        employment = normalize_employment_type(d.get("employmentType"))
        skills = as_string_list(d.get("skills") or d.get("technologies") or [])
        url = _strip_utm(first_str(d, "detailsPageUrl", "url"))
        apply_hint = first_str(d, "applyUrl", "applicationUrl")

        meta: dict[str, Any] = {}
        easy = first_bool(d, "easyApply")
        if easy is not None:
            meta["easy_apply"] = easy
        employer_type = first_str(d, "employerType")
        if employer_type:
            meta["employer_type"] = employer_type
        if workplace:
            meta["workplace_types"] = workplace
        company_page = first_str(d, "companyPageUrl")
        if company_page:
            meta["company_page_url"] = company_page
        if d.get("willingToSponsor") is not None:
            meta["willing_to_sponsor"] = bool(d.get("willingToSponsor"))
        if apply_hint:
            meta["application_url"] = apply_hint

        visa = None
        if d.get("willingToSponsor") is True:
            visa = True
        elif d.get("willingToSponsor") is False:
            visa = False

        return {
            "title": first_str(d, "title"),
            "company": first_str(d, "companyName", "company"),
            "description": clean_description(d.get("summary") or d.get("description") or ""),
            "skills": skills,
            "location": location,
            "salary_range": salary,
            "employment_type": employment,
            "equity_range": None,
            "url": url,
            "language": "en",
            "posted_date": parse_posted_date(d.get("postedDate") or d.get("modifiedDate")),
            "remote_modality": remote_modality,
            "visa_sponsorship_available": visa,
            "source_metadata": meta,
        }
