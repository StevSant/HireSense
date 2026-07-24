from __future__ import annotations

import json
from pathlib import Path

import pytest

from hiresense.ingestion.adapters import (
    GlassdoorAdapter,
    IndeedAdapter,
    MonsterAdapter,
    WellfoundAdapter,
)
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import (
    GlassdoorNormalizer,
    IndeedNormalizer,
    MonsterNormalizer,
    WellfoundNormalizer,
)
from hiresense.kernel.value_objects import SourceType


@pytest.fixture()
def import_dir(tmp_path: Path) -> Path:
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_indeed_import_happy_path(import_dir: Path) -> None:
    _write_jsonl(
        import_dir / "indeed_jobs.jsonl",
        [
            {
                "id": "ind-1",
                "title": "Backend Engineer",
                "company": "Acme",
                "url": "https://www.indeed.com/viewjob?jk=ind-1",
                "location": "Remote",
                "remote": True,
                "salary_range": "$140k-$170k",
                "salary_currency": "USD",
                "salary_period": "year",
                "employment_type": "full_time",
                "easy_apply": True,
                "description": "Build APIs",
                "posted_date": "2026-07-01",
            },
            {"id": "bad", "title": "", "company": ""},
        ],
    )
    adapter = IndeedAdapter(import_dir=str(import_dir))
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source_id == "ind-1"
    assert adapter.source_type() == SourceType.MANUAL
    out = IndeedNormalizer().normalize(jobs[0])
    assert out["remote_modality"] == "remote"
    assert out["source_metadata"]["easy_apply"] is True
    assert out["source_metadata"]["salary_currency"] == "USD"


@pytest.mark.asyncio
async def test_wellfound_import_startup_fields(import_dir: Path) -> None:
    _write_jsonl(
        import_dir / "wellfound_jobs.jsonl",
        [
            {
                "id": "wf-1",
                "title": "Founding Engineer",
                "company": "StartupCo",
                "url": "https://wellfound.com/jobs/1",
                "salary_min": 150000,
                "salary_max": 180000,
                "salary_currency": "USD",
                "equity_range": "0.5% – 1.5%",
                "company_stage": "Series A",
                "team_size": "11-50",
                "funding": "$12M",
                "visa_sponsorship_available": True,
                "skills": ["Rust", "Postgres"],
                "remote": True,
            }
        ],
    )
    adapter = WellfoundAdapter(import_dir=str(import_dir))
    jobs = await adapter.fetch_jobs()
    out = WellfoundNormalizer().normalize(jobs[0])
    assert out["equity_range"] == "0.5% – 1.5%"
    assert out["source_metadata"]["company_stage"] == "Series A"
    assert out["visa_sponsorship_available"] is True
    assert "Rust" in out["skills"]


@pytest.mark.asyncio
async def test_glassdoor_strips_reviews(import_dir: Path) -> None:
    _write_jsonl(
        import_dir / "glassdoor_jobs.jsonl",
        [
            {
                "id": "gd-1",
                "title": "Data Analyst",
                "company": "BigCo",
                "url": "https://www.glassdoor.com/job-listing/gd-1",
                "company_rating": 4.2,
                "company_size": "1001-5000",
                "industry": "Software",
                "headquarters": "SF",
                "reviews": [{"text": "should not persist"}],
            }
        ],
    )
    adapter = GlassdoorAdapter(import_dir=str(import_dir))
    jobs = await adapter.fetch_jobs()
    out = GlassdoorNormalizer().normalize(jobs[0])
    assert out["source_metadata"]["company_rating"] == 4.2
    assert "reviews" not in out["source_metadata"]


@pytest.mark.asyncio
async def test_monster_missing_file_returns_empty(import_dir: Path) -> None:
    adapter = MonsterAdapter(import_dir=str(import_dir))
    assert await adapter.fetch_jobs() == []


@pytest.mark.asyncio
async def test_import_path_traversal_rejected(import_dir: Path) -> None:
    adapter = IndeedAdapter(import_dir=str(import_dir))
    with pytest.raises(ValueError, match="escapes"):
        await adapter.fetch_jobs({"file_path": "../secrets.json"})


def test_monster_normalizer_employment() -> None:
    raw = RawJobListing(
        source="monster",
        source_id="m1",
        raw_data={
            "title": "Java Dev",
            "company": "Corp",
            "url": "https://monster.com/job/m1",
            "employment_type": "contract",
            "experience_level": "mid",
            "description": "Java",
        },
    )
    out = MonsterNormalizer().normalize(raw)
    assert out["employment_type"] == "contract"
    assert out["source_metadata"]["experience_level"] == "mid"
