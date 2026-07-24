"""Y Combinator Work at a Startup — public Inertia JSON embedded in HTML."""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
from typing import Any
from urllib.parse import urljoin

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)

_DATA_PAGE_RE = re.compile(r'data-page="([^"]+)"')


def extract_inertia_props(page_html: str) -> dict[str, Any]:
    match = _DATA_PAGE_RE.search(page_html)
    if not match:
        raise ValueError("Work at a Startup page missing Inertia data-page payload")
    raw = html_lib.unescape(match.group(1))
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Inertia data-page is not an object")
    props = data.get("props")
    if not isinstance(props, dict):
        raise ValueError("Inertia props missing")
    return props


class YCJobsAdapter:
    """Parse public structured job lists from workatastartup.com HTML.

    Role index pages embed a `jobs` array in Inertia props. Optional company
    page enrichment adds equity/visa/experience when enabled.
    """

    def __init__(
        self,
        http_client: Any,
        *,
        base_url: str = "https://www.workatastartup.com",
        roles: list[str] | None = None,
        remote_only: bool = False,
        enrich_companies: bool = True,
        company_enrich_limit: int = 25,
        result_limit: int = 200,
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._roles = roles or [
            "software-engineer",
            "product",
            "designer",
            "science",
        ]
        self._remote_only = remote_only
        self._enrich_companies = enrich_companies
        self._company_enrich_limit = max(0, company_enrich_limit)
        self._result_limit = max(1, result_limit)
        self.last_pages_fetched = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "yc_jobs"

    def source_type(self) -> SourceType:
        return SourceType.SCRAPER

    async def _get_html(self, path: str) -> str:
        url = urljoin(self._base_url + "/", path.lstrip("/"))
        response = await self._http.get(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; HireSense/1.0; +https://github.com/StevSant/HireSense)"
                ),
            },
        )
        response.raise_for_status()
        return response.text

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        self.last_pages_fetched = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0
        remote_only = bool((filters or {}).get("remote_only", self._remote_only))
        roles = (filters or {}).get("roles") or self._roles
        if isinstance(roles, str):
            roles = [r.strip() for r in roles.split(",") if r.strip()]

        jobs_by_id: dict[str, dict[str, Any]] = {}
        for role in roles:
            path = f"/jobs/role/{role}"
            if remote_only:
                path = f"{path}?remote=true"
            try:
                page_html = await self._get_html(path)
                props = extract_inertia_props(page_html)
            except Exception:
                self.last_parse_failures += 1
                logger.exception("Failed to parse YC jobs page for role=%s", role)
                continue
            self.last_pages_fetched += 1
            page_jobs = props.get("jobs") or []
            if not isinstance(page_jobs, list):
                self.last_parse_failures += 1
                continue
            for item in page_jobs:
                if not isinstance(item, dict) or item.get("id") is None:
                    self.last_rejected_malformed += 1
                    continue
                source_id = str(item["id"])
                enriched = dict(item)
                enriched["_role_path"] = role
                jobs_by_id[source_id] = enriched
            if len(jobs_by_id) >= self._result_limit:
                break

        if self._enrich_companies and self._company_enrich_limit > 0:
            await self._enrich_from_companies(jobs_by_id)

        listings: list[RawJobListing] = []
        for source_id, data in list(jobs_by_id.items())[: self._result_limit]:
            listings.append(RawJobListing(source="yc_jobs", source_id=source_id, raw_data=data))
        return listings

    async def _enrich_from_companies(self, jobs_by_id: dict[str, dict[str, Any]]) -> None:
        slugs: list[str] = []
        seen: set[str] = set()
        for data in jobs_by_id.values():
            slug = data.get("companySlug")
            if isinstance(slug, str) and slug and slug not in seen:
                seen.add(slug)
                slugs.append(slug)
            if len(slugs) >= self._company_enrich_limit:
                break

        detail_by_id: dict[str, dict[str, Any]] = {}
        company_meta: dict[str, dict[str, Any]] = {}
        for slug in slugs:
            try:
                page_html = await self._get_html(f"/companies/{slug}")
                props = extract_inertia_props(page_html)
            except Exception:
                self.last_parse_failures += 1
                logger.debug("YC company enrich failed for %s", slug, exc_info=True)
                continue
            self.last_pages_fetched += 1
            company = props.get("company")
            if not isinstance(company, dict):
                continue
            company_meta[slug] = {
                k: company.get(k)
                for k in (
                    "name",
                    "slug",
                    "batch",
                    "oneLiner",
                    "website",
                    "teamSize",
                    "industry",
                    "location",
                    "description",
                )
                if company.get(k) is not None
            }
            for job in company.get("jobs") or []:
                if isinstance(job, dict) and job.get("id") is not None:
                    detail_by_id[str(job["id"])] = job

        for source_id, data in jobs_by_id.items():
            detail = detail_by_id.get(source_id)
            if detail:
                for key in (
                    "salaryRange",
                    "equityRange",
                    "sponsorsVisa",
                    "minExperience",
                    "jobType",
                    "location",
                    "description",
                    "skills",
                    "technologies",
                ):
                    if detail.get(key) is not None and data.get(key) is None:
                        data[key] = detail[key]
            slug = data.get("companySlug")
            if isinstance(slug, str) and slug in company_meta:
                data["_company"] = company_meta[slug]
