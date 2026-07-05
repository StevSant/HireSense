from pydantic_settings import BaseSettings


class PortalsSettings(BaseSettings):
    """ATS portal scanning config + per-ATS public API URLs."""

    # Portal scanning
    portals_config_path: str = "ingestion/config/portals.yml"
    portal_scan_timeout: float = 30.0
    greenhouse_api_url: str = "https://boards-api.greenhouse.io/v1/boards"
    lever_api_url: str = "https://api.lever.co/v0/postings"
    ashby_api_url: str = "https://api.ashbyhq.com/posting-api/job-board"
    # Workable public widget API: {base}/{board_id} where board_id is the
    # account subdomain. Returns the account's complete published job set.
    workable_api_url: str = "https://apply.workable.com/api/v1/widget/accounts"
    # SmartRecruiters public Posting API: {base}/{board_id}/postings where
    # board_id is the company identifier.
    smartrecruiters_api_url: str = "https://api.smartrecruiters.com/v1/companies"
    # Recruitee public Offers API. {company} is templated with the company
    # subdomain (the portal board_id) at fetch time.
    recruitee_api_url: str = "https://{company}.recruitee.com/api"
