"""Import all ORM models so Base.metadata is fully populated for Alembic."""

from hiresense.admin.infrastructure import (  # noqa: F401
    LLMAuditLog,
    LLMFeatureOverride,
    LLMSettings,
    LLMUsageLog,
)
from hiresense.applications.infrastructure import (  # noqa: F401
    ApplicationCoverLetterOrm,
    ApplicationCvOptimizationOrm,
    ApplicationInterviewPrepOrm,
    ApplicationJobSnapshotOrm,
    ApplicationMatchOrm,
)
from hiresense.autohunt.infrastructure import DigestOrm  # noqa: F401
from hiresense.cover_letter_templates.infrastructure import CoverLetterTemplateOrm  # noqa: F401
from hiresense.ingestion.infrastructure import IngestedJob, JobMatchCache  # noqa: F401
from hiresense.interview.infrastructure import StoryOrm  # noqa: F401
from hiresense.outreach.infrastructure import OutreachEventOrm  # noqa: F401
from hiresense.portfolio.infrastructure import PortfolioProjectOrm  # noqa: F401
from hiresense.preference.infrastructure import FeedbackSignalOrm, PreferenceModelOrm  # noqa: F401
from hiresense.profile.infrastructure import ProfileOrm  # noqa: F401
from hiresense.research.infrastructure import CompanyResearchOrm  # noqa: F401
from hiresense.tracking.infrastructure import TrackedApplicationOrm  # noqa: F401
