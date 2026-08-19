"""Typed capability descriptors for every HireSense job source."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from hiresense.ingestion.domain.apply_access import ApplyAccess
from hiresense.shared.kernel.value_objects import SourceType

ClosureStrategy = Literal["snapshot", "url_probe", "expiry", "none"]
IntegrationMethod = Literal[
    "official_api",
    "official_rss",
    "public_structured",
    "public_html",
    "import_fallback",
    "manual",
]


class SourceCapabilities(BaseModel):
    """Declarative description of what a source can do and how it integrates."""

    source: str
    display_name: str
    source_type: SourceType
    integration: IntegrationMethod
    enabled_by_default: bool = False
    requires_credentials: bool = False
    supports_keyword_search: bool = False
    supports_location_search: bool = False
    supports_remote_filter: bool = False
    supports_pagination: bool = False
    provides_salary: bool = False
    provides_equity: bool = False
    provides_company_metadata: bool = False
    provides_technology_tags: bool = False
    snapshot_source: bool = False
    reliable_closure_detection: bool = False
    closure_strategy: ClosureStrategy = "url_probe"
    # Whether a candidate can actually reach the application form from the
    # URL we store. Audited per board — see apply_access.py.
    apply_access: ApplyAccess = ApplyAccess.UNKNOWN
    # One short sentence shown to the user when apply_access is not DIRECT.
    apply_access_note: str = ""
    limitations: str = ""


# Precedence for cross-source consolidation (lower = preferred).
# Direct company ATS listings beat third-party aggregators.
SOURCE_TIER: dict[str, int] = {
    "greenhouse": 0,
    "lever": 0,
    "ashby": 0,
    "workable": 0,
    "smartrecruiters": 0,
    "recruitee": 0,
    "workday": 0,
    "yc_jobs": 1,
    "wellfound": 1,
    "getonboard": 2,
    "remotive": 2,
    "remoteok": 2,
    "jobicy": 2,
    "himalayas": 2,
    "weworkremotely": 2,
    "arbeitnow": 2,
    "themuse": 2,
    "hn_hiring": 2,
    "crunchboard": 3,
    "dice": 3,
    "adzuna": 3,
    "linkedin": 3,
    "indeed": 4,
    "monster": 4,
    "glassdoor": 4,
    "csv": 5,
}


def source_tier(source: str) -> int:
    return SOURCE_TIER.get(source, 3)


SOURCE_CAPABILITY_REGISTRY: dict[str, SourceCapabilities] = {
    "remotive": SourceCapabilities(
        source="remotive",
        display_name="Remotive",
        apply_access=ApplyAccess.DIRECT,
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        supports_keyword_search=True,
        provides_salary=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
    ),
    "remoteok": SourceCapabilities(
        source="remoteok",
        display_name="RemoteOK",
        apply_access=ApplyAccess.PAID_REQUIRED,
        apply_access_note=(
            "RemoteOK routes Apply through /l/<id>, which serves its paid premium "
            "page; the employer URL is never exposed."
        ),
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        provides_salary=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
    ),
    "jobicy": SourceCapabilities(
        source="jobicy",
        display_name="Jobicy",
        apply_access=ApplyAccess.UNKNOWN,
        apply_access_note=(
            "Job pages load normally for humans but sit behind a Cloudflare challenge "
            "that blocks automated clients, so the apply hop has not been audited."
        ),
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        provides_salary=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
    ),
    "himalayas": SourceCapabilities(
        source="himalayas",
        display_name="Himalayas",
        apply_access=ApplyAccess.ACCOUNT_REQUIRED,
        apply_access_note=(
            "Apply redirects to himalayas.app/signup/talent; a free Himalayas account is required."
        ),
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        supports_pagination=True,
        provides_technology_tags=True,
        reliable_closure_detection=True,
        closure_strategy="expiry",
        limitations="Public pages block URL probes; closure uses declared expiry.",
    ),
    "hn_hiring": SourceCapabilities(
        source="hn_hiring",
        display_name="HN Who is Hiring",
        apply_access=ApplyAccess.DIRECT,
        source_type=SourceType.SCRAPER,
        integration="public_structured",
        enabled_by_default=True,
        closure_strategy="none",
        limitations="Age-based staleness only; no reliable per-URL closure signal.",
    ),
    "weworkremotely": SourceCapabilities(
        source="weworkremotely",
        display_name="We Work Remotely",
        apply_access=ApplyAccess.ACCOUNT_REQUIRED,
        apply_access_note=(
            "Apply redirects to the We Work Remotely job-seeker registration page; "
            "a free account is required."
        ),
        source_type=SourceType.RSS,
        integration="official_rss",
        enabled_by_default=True,
        closure_strategy="url_probe",
    ),
    "getonboard": SourceCapabilities(
        source="getonboard",
        display_name="Get on Board",
        apply_access=ApplyAccess.ACCOUNT_REQUIRED,
        apply_access_note=(
            "Applications are submitted on Get on Board; a free account (email or "
            "Google/LinkedIn/GitHub) is required."
        ),
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        supports_keyword_search=True,
        provides_salary=True,
        provides_company_metadata=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
    ),
    "linkedin": SourceCapabilities(
        source="linkedin",
        display_name="LinkedIn",
        apply_access=ApplyAccess.ACCOUNT_REQUIRED,
        apply_access_note=("Applying requires being signed in to LinkedIn."),
        source_type=SourceType.SCRAPER,
        integration="public_html",
        enabled_by_default=True,
        supports_keyword_search=True,
        supports_location_search=True,
        supports_remote_filter=True,
        supports_pagination=True,
        closure_strategy="url_probe",
        limitations="Fragile guest HTML scraper; ToS-risky and rate-limit sensitive.",
    ),
    "arbeitnow": SourceCapabilities(
        source="arbeitnow",
        display_name="Arbeitnow",
        apply_access=ApplyAccess.DIRECT,
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        supports_keyword_search=True,
        supports_pagination=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
    ),
    "themuse": SourceCapabilities(
        source="themuse",
        display_name="The Muse",
        apply_access=ApplyAccess.DIRECT,
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        supports_pagination=True,
        provides_company_metadata=True,
        closure_strategy="url_probe",
    ),
    "adzuna": SourceCapabilities(
        source="adzuna",
        display_name="Adzuna",
        apply_access=ApplyAccess.DIRECT,
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=False,
        requires_credentials=True,
        supports_keyword_search=True,
        supports_location_search=True,
        supports_pagination=True,
        provides_salary=True,
        closure_strategy="url_probe",
        limitations="Requires ADZUNA_APP_ID and ADZUNA_APP_KEY.",
    ),
    "csv": SourceCapabilities(
        source="csv",
        display_name="CSV Import",
        apply_access=ApplyAccess.UNKNOWN,
        source_type=SourceType.MANUAL,
        integration="manual",
        enabled_by_default=False,
        closure_strategy="none",
    ),
    "workday": SourceCapabilities(
        source="workday",
        display_name="Workday",
        apply_access=ApplyAccess.DIRECT,
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=False,
        supports_pagination=True,
        snapshot_source=True,
        reliable_closure_detection=True,
        closure_strategy="snapshot",
        limitations="Needs the public careers/jobs URL (or equivalent jobs endpoint) to derive tenant/site.",
    ),
    "dice": SourceCapabilities(
        source="dice",
        display_name="Dice",
        apply_access=ApplyAccess.DIRECT,
        source_type=SourceType.API,
        integration="official_api",
        enabled_by_default=True,
        supports_keyword_search=True,
        supports_location_search=True,
        supports_remote_filter=True,
        supports_pagination=True,
        provides_salary=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
        limitations="Uses Dice's official MCP search_jobs tool over HTTPS JSON-RPC.",
    ),
    "crunchboard": SourceCapabilities(
        source="crunchboard",
        display_name="CrunchBoard",
        apply_access=ApplyAccess.UNKNOWN,
        source_type=SourceType.RSS,
        integration="official_rss",
        enabled_by_default=False,
        provides_salary=False,
        closure_strategy="url_probe",
        limitations=(
            "Feed is dead: crunchboard.com/jobs.rss 301-redirects to jobboard.io, so "
            "every fetch parses a marketing homepage and yields zero jobs. Disabled "
            "until TechCrunch restores the feed."
        ),
    ),
    "yc_jobs": SourceCapabilities(
        source="yc_jobs",
        display_name="Y Combinator Jobs",
        apply_access=ApplyAccess.ACCOUNT_REQUIRED,
        apply_access_note=("Applying requires a free Work at a Startup account."),
        source_type=SourceType.SCRAPER,
        integration="public_structured",
        enabled_by_default=True,
        supports_remote_filter=True,
        provides_salary=True,
        provides_equity=True,
        provides_company_metadata=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
        limitations="Parses public Work at a Startup Inertia JSON embedded in HTML.",
    ),
    "indeed": SourceCapabilities(
        source="indeed",
        display_name="Indeed",
        apply_access=ApplyAccess.UNKNOWN,
        source_type=SourceType.MANUAL,
        integration="import_fallback",
        enabled_by_default=False,
        supports_keyword_search=True,
        supports_location_search=True,
        supports_remote_filter=True,
        provides_salary=True,
        provides_company_metadata=True,
        closure_strategy="url_probe",
        limitations=(
            "Indeed shut down its public Jobs/Publisher APIs. Live scraping is blocked "
            "and ToS-restricted. Use JSONL/CSV import under the configured import dir."
        ),
    ),
    "wellfound": SourceCapabilities(
        source="wellfound",
        display_name="Wellfound",
        apply_access=ApplyAccess.ACCOUNT_REQUIRED,
        apply_access_note=("Applying requires a free Wellfound account."),
        source_type=SourceType.MANUAL,
        integration="import_fallback",
        enabled_by_default=False,
        supports_keyword_search=True,
        supports_remote_filter=True,
        provides_salary=True,
        provides_equity=True,
        provides_company_metadata=True,
        provides_technology_tags=True,
        closure_strategy="url_probe",
        limitations=(
            "No public API; site is DataDome-protected. Import JSONL with startup "
            "metadata (stage, funding, equity, visa, skills)."
        ),
    ),
    "glassdoor": SourceCapabilities(
        source="glassdoor",
        display_name="Glassdoor",
        apply_access=ApplyAccess.UNKNOWN,
        source_type=SourceType.MANUAL,
        integration="import_fallback",
        enabled_by_default=False,
        supports_keyword_search=True,
        supports_location_search=True,
        provides_salary=True,
        provides_company_metadata=True,
        closure_strategy="url_probe",
        limitations=(
            "Partner API shut down; search is Cloudflare-protected. Import public job "
            "fields only — never reviews or login-gated content."
        ),
    ),
    "monster": SourceCapabilities(
        source="monster",
        display_name="Monster",
        apply_access=ApplyAccess.UNKNOWN,
        source_type=SourceType.MANUAL,
        integration="import_fallback",
        enabled_by_default=False,
        supports_keyword_search=True,
        supports_location_search=True,
        supports_remote_filter=True,
        provides_salary=True,
        closure_strategy="url_probe",
        limitations="Historical RSS is dead and search is bot-protected. Use JSONL/CSV import.",
    ),
}


def list_source_capabilities() -> list[SourceCapabilities]:
    return list(SOURCE_CAPABILITY_REGISTRY.values())


def get_source_capabilities(source: str) -> SourceCapabilities | None:
    return SOURCE_CAPABILITY_REGISTRY.get(source)


def source_apply_access(source: str) -> ApplyAccess:
    """Apply-access for a source; UNKNOWN for anything not in the registry."""
    caps = SOURCE_CAPABILITY_REGISTRY.get(source)
    return caps.apply_access if caps else ApplyAccess.UNKNOWN


def source_apply_access_note(source: str) -> str:
    caps = SOURCE_CAPABILITY_REGISTRY.get(source)
    return caps.apply_access_note if caps else ""
