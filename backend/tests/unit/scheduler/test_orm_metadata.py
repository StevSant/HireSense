from hiresense.infrastructure.database import Base
# Importing the registry must register the scheduler tables on Base.metadata.
import hiresense.infrastructure.registry  # noqa: F401


def test_scheduler_tables_registered():
    tables = set(Base.metadata.tables)
    assert "scheduler_job_runs" in tables
    assert "scheduler_job_toggles" in tables
