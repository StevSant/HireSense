import pytest

from hiresense.ingestion.adapters import CSVImportAdapter
from hiresense.kernel.value_objects import SourceType


@pytest.mark.asyncio
async def test_csv_import_reads_file(tmp_path) -> None:
    csv_content = (
        "title,company,description,skills,location,url\n"
        'Backend Engineer,Acme,"Build APIs",python;fastapi,Remote,https://example.com/1\n'
        'Frontend Dev,Beta,"Build UIs",angular;typescript,Remote,https://example.com/2\n'
    )
    (tmp_path / "jobs.csv").write_text(csv_content, encoding="utf-8")
    adapter = CSVImportAdapter(import_dir=str(tmp_path))
    jobs = await adapter.fetch_jobs(filters={"file_path": "jobs.csv"})
    assert len(jobs) == 2
    assert jobs[0].source == "csv"
    assert jobs[0].raw_data["title"] == "Backend Engineer"
    assert jobs[1].raw_data["company"] == "Beta"


@pytest.mark.asyncio
async def test_csv_import_rejects_path_traversal(tmp_path) -> None:
    outside = tmp_path / "outside.csv"
    outside.write_text("title\nEscape\n", encoding="utf-8")
    import_dir = tmp_path / "imports"
    import_dir.mkdir()
    adapter = CSVImportAdapter(import_dir=str(import_dir))
    with pytest.raises(ValueError, match="escapes the import directory"):
        await adapter.fetch_jobs(filters={"file_path": "../outside.csv"})


@pytest.mark.asyncio
async def test_csv_import_rejects_absolute_path_outside_dir(tmp_path) -> None:
    outside = tmp_path / "outside.csv"
    outside.write_text("title\nEscape\n", encoding="utf-8")
    import_dir = tmp_path / "imports"
    import_dir.mkdir()
    adapter = CSVImportAdapter(import_dir=str(import_dir))
    with pytest.raises(ValueError, match="escapes the import directory"):
        await adapter.fetch_jobs(filters={"file_path": str(outside)})


def test_csv_source_name() -> None:
    adapter = CSVImportAdapter()
    assert adapter.source_name() == "csv"
    assert adapter.source_type() == SourceType.MANUAL
