import tempfile
from pathlib import Path

import pytest

from hiresense.ingestion.adapters.csv_import import CSVImportAdapter
from hiresense.kernel.value_objects import SourceType


@pytest.mark.asyncio
async def test_csv_import_reads_file() -> None:
    csv_content = (
        "title,company,description,skills,location,url\n"
        'Backend Engineer,Acme,"Build APIs",python;fastapi,Remote,https://example.com/1\n'
        'Frontend Dev,Beta,"Build UIs",angular;typescript,Remote,https://example.com/2\n'
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    adapter = CSVImportAdapter()
    jobs = await adapter.fetch_jobs(filters={"file_path": csv_path})
    assert len(jobs) == 2
    assert jobs[0].source == "csv"
    assert jobs[0].raw_data["title"] == "Backend Engineer"
    assert jobs[1].raw_data["company"] == "Beta"
    Path(csv_path).unlink()


def test_csv_source_name() -> None:
    adapter = CSVImportAdapter()
    assert adapter.source_name() == "csv"
    assert adapter.source_type() == SourceType.MANUAL
