"""Import all ORM models so Base.metadata is fully populated for Alembic."""

from hiresense.admin.infrastructure import (  # noqa: F401
    LLMAuditLog,
    LLMFeatureOverride,
    LLMSettings,
    LLMUsageLog,
)
from hiresense.cover_letter_templates.domain.orm import CoverLetterTemplateOrm  # noqa: F401
from hiresense.ingestion.infrastructure import IngestedJob  # noqa: F401
from hiresense.interview.domain.models import Story  # noqa: F401
from hiresense.profile.domain.models import Profile  # noqa: F401
from hiresense.research.domain.models import CompanyResearch  # noqa: F401
from hiresense.tracking.domain.models import TrackedApplication  # noqa: F401
