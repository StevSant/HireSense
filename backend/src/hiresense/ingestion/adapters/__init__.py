from hiresense.ingestion.adapters.adzuna import AdzunaAdapter
from hiresense.ingestion.adapters.arbeitnow import ArbeitnowAdapter
from hiresense.ingestion.adapters.ashby_adapter import AshbyAdapter
from hiresense.ingestion.adapters.auto_portal_adapter import AutoPortalAdapter
from hiresense.ingestion.adapters.crunchboard import CrunchBoardAdapter
from hiresense.ingestion.adapters.csv_import import CSVImportAdapter
from hiresense.ingestion.adapters.dice import DiceAdapter
from hiresense.ingestion.adapters.getonboard import GetOnBoardAdapter
from hiresense.ingestion.adapters.generic_scraper_adapter import GenericScraperAdapter
from hiresense.ingestion.adapters.greenhouse_adapter import GreenhouseAdapter
from hiresense.ingestion.adapters.himalayas import HimalayasAdapter
from hiresense.ingestion.adapters.hn_hiring import HNHiringAdapter
from hiresense.ingestion.adapters.jobicy import JobicyAdapter
from hiresense.ingestion.adapters.lever_adapter import LeverAdapter
from hiresense.ingestion.adapters.linkedin import LinkedInAdapter
from hiresense.ingestion.adapters.recruitee_adapter import RecruiteeAdapter
from hiresense.ingestion.adapters.remoteok import RemoteOKAdapter
from hiresense.ingestion.adapters.remotive import RemotiveAdapter
from hiresense.ingestion.adapters.smartrecruiters_adapter import SmartRecruitersAdapter
from hiresense.ingestion.adapters.structured_import import (
    GlassdoorAdapter,
    IndeedAdapter,
    MonsterAdapter,
    WellfoundAdapter,
)
from hiresense.ingestion.adapters.the_muse import TheMuseAdapter
from hiresense.ingestion.adapters.thoughtworks_adapter import ThoughtworksAdapter
from hiresense.ingestion.adapters.weworkremotely import WeWorkRemotelyAdapter
from hiresense.ingestion.adapters.workable_adapter import WorkableAdapter
from hiresense.ingestion.adapters.workday_adapter import WorkdayAdapter
from hiresense.ingestion.adapters.yc_jobs import YCJobsAdapter
from hiresense.ingestion.adapters.globant_adapter import GlobantAdapter

__all__ = [
    "AdzunaAdapter",
    "ArbeitnowAdapter",
    "AshbyAdapter",
    "AutoPortalAdapter",
    "CrunchBoardAdapter",
    "CSVImportAdapter",
    "DiceAdapter",
    "GenericScraperAdapter",
    "GetOnBoardAdapter",
    "GlassdoorAdapter",
    "GlobantAdapter",
    "GreenhouseAdapter",
    "HimalayasAdapter",
    "HNHiringAdapter",
    "IndeedAdapter",
    "JobicyAdapter",
    "LeverAdapter",
    "LinkedInAdapter",
    "MonsterAdapter",
    "RecruiteeAdapter",
    "RemoteOKAdapter",
    "RemotiveAdapter",
    "SmartRecruitersAdapter",
    "TheMuseAdapter",
    "ThoughtworksAdapter",
    "WellfoundAdapter",
    "WeWorkRemotelyAdapter",
    "WorkableAdapter",
    "WorkdayAdapter",
    "YCJobsAdapter",
]
