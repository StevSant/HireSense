from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers._import_fields import (
    as_string_list,
    clean_description,
    first_str,
    normalize_employment_type,
    normalize_remote_modality,
)


class YCJobsNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        company = first_str(d, "companyName", "company")
        title = first_str(d, "title")
        location = first_str(d, "location")
        salary = first_str(d, "salary", "salaryRange") or None
        equity = first_str(d, "equityRange", "equity") or None
        employment = normalize_employment_type(d.get("jobType") or d.get("type"))
        remote_modality = normalize_remote_modality(location=location)
        skills = as_string_list(d.get("skills") or d.get("technologies") or [])
        role_type = first_str(d, "roleType")
        if role_type and role_type not in skills:
            skills = [role_type, *skills]

        slug = first_str(d, "companySlug")
        job_id = d.get("id") or raw.source_id
        # Prefer the per-job URL so URL-probe revalidation can detect closure of
        # a single role. Company pages stay live after one job is removed.
        url = f"https://www.workatastartup.com/jobs/{job_id}" if job_id else ""

        meta: dict[str, Any] = {}
        if slug:
            meta["company_url"] = f"https://www.workatastartup.com/companies/{slug}"
        batch = first_str(d, "companyBatch")
        if batch:
            meta["yc_batch"] = batch
        one_liner = first_str(d, "companyOneLiner")
        if one_liner:
            meta["company_one_liner"] = one_liner
        if role_type:
            meta["role_type"] = role_type
        apply_url = first_str(d, "applyUrl")
        if apply_url:
            meta["application_url"] = apply_url
        min_exp = d.get("minExperience")
        if min_exp is not None:
            meta["min_experience"] = min_exp
        sponsors = d.get("sponsorsVisa")
        visa = None
        if isinstance(sponsors, bool):
            visa = sponsors
            meta["sponsors_visa"] = sponsors
        elif isinstance(sponsors, str) and sponsors.strip():
            meta["sponsors_visa"] = sponsors.strip()
            lower = sponsors.lower()
            if "sponsor" in lower and "not" not in lower and "no " not in lower:
                visa = True
            elif "citizen" in lower or "no sponsor" in lower:
                visa = False
        company_extra = d.get("_company")
        if isinstance(company_extra, dict):
            for key, out_key in (
                ("batch", "yc_batch"),
                ("teamSize", "team_size"),
                ("industry", "industry"),
                ("website", "company_website"),
                ("description", "company_description"),
                ("location", "company_location"),
            ):
                if company_extra.get(key) is not None and out_key not in meta:
                    meta[out_key] = company_extra[key]

        description_parts = []
        if one_liner:
            description_parts.append(one_liner)
        if d.get("description"):
            description_parts.append(clean_description(d.get("description")))
        elif role_type:
            description_parts.append(f"Role type: {role_type}")
        description = "\n\n".join(p for p in description_parts if p)

        return {
            "title": title,
            "company": company,
            "description": description,
            "skills": skills,
            "location": location,
            "salary_range": salary,
            "employment_type": employment,
            "equity_range": equity,
            "url": url,
            "language": "en",
            "posted_date": None,
            "remote_modality": remote_modality,
            "visa_sponsorship_available": visa,
            "source_metadata": meta,
        }
