"""Import all ORM models so Base.metadata is fully populated for Alembic."""

from hiresense.tracking.domain.models import TrackedApplication  # noqa: F401
