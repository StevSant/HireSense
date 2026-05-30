"""Import all ORM models so Base.metadata is fully populated for Alembic."""

from hiresense.admin.infrastructure import (  # noqa: F401
    LLMAuditLog,
    LLMFeatureOverride,
    LLMSettings,
    LLMUsageLog,
)
from hiresense.applications.domain.models import (  # noqa: F401
    ApplicationCoverLetter,
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
)
from hiresense.cover_letter_templates.infrastructure import CoverLetterTemplateOrm  # noqa: F401
from hiresense.ingestion.infrastructure import IngestedJob, JobMatchCache  # noqa: F401
from hiresense.interview.infrastructure import StoryOrm  # noqa: F401
from hiresense.profile.domain.models import Profile  # noqa: F401
from hiresense.research.infrastructure import CompanyResearchOrm  # noqa: F401
from hiresense.tracking.domain.models import TrackedApplication  # noqa: F401
