from __future__ import annotations

import pytest

from hiresense.analytics.domain import CompBenchmarkService, SalaryParser
from hiresense.analytics.infrastructure.corpus_repository import CorpusJobRow


class _Emb:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3]]


class _Store:
    def __init__(self, ids):
        self._ids = ids

    async def search(self, query_embedding, *, top_k=10, filters=None):
        return [type("R", (), {"id": i, "score": 1.0})() for i in self._ids]


class _Corpus:
    def __init__(self, rows, tracked_salaries=None):
        self._rows = rows
        self._tracked = tracked_salaries or {}

    def rows_for_ids(self, ids):
        return {i: self._rows[i] for i in ids if i in self._rows}

    def descriptions_for_ids(self, ids):
        return {i: "Senior role" for i in ids if i in self._rows}

    def salary_strings_for_ids(self, ids):
        return {i: self._tracked.get(i) for i in ids}


class _Tracking:
    def __init__(self, job_ids):
        self._apps = [type("A", (), {"job_id": j, "status": "applied"})() for j in job_ids]

    def list(self):
        return self._apps


def _row(jid, salary, title="Senior Backend Engineer"):
    return CorpusJobRow(
        id=jid, title=title, company="Co", location="Remote", source="x",
        salary_range=salary, posted_date=None, remote_modality="remote",
        status="open", quality="ok",
    )


@pytest.mark.asyncio
async def test_pipeline_median_vs_market():
    # Market: 5 matched jobs at $100k–$140k (mids 110..130k).
    rows = {f"m{i}": _row(f"m{i}", f"${100 + i * 10}k-${120 + i * 10}k") for i in range(5)}
    # Candidate's tracked apps point at two jobs paying ~ $90k and $95k → below market.
    rows["t1"] = _row("t1", "$80k-$100k")
    rows["t2"] = _row("t2", "$90k-$100k")
    corpus = _Corpus(rows, tracked_salaries={"t1": "$80k-$100k", "t2": "$90k-$100k"})
    svc = CompBenchmarkService(
        embedding=_Emb(), vector_store=_Store([f"m{i}" for i in range(5)]), corpus=corpus,
        salary_parser=SalaryParser(), tracking_read=_Tracking(["t1", "t2"]),
        top_k=50, min_sample=5,
    )

    out = await svc.compute(profile_skills=["python"], summary="backend")

    assert out.insufficient_data is False
    assert out.currency == "USD"
    assert out.your_sample_size == 2
    assert out.your_median_annual is not None
    assert out.your_median_annual < out.median_annual  # candidate is below market
    assert out.ask_min_annual == out.median_annual and out.ask_max_annual == out.p75_annual


@pytest.mark.asyncio
async def test_no_vector_store_is_insufficient():
    svc = CompBenchmarkService(
        embedding=_Emb(), vector_store=None, corpus=_Corpus({}), salary_parser=SalaryParser(),
        tracking_read=None, top_k=50, min_sample=5,
    )
    out = await svc.compute(profile_skills=["python"], summary="x")
    assert out.insufficient_data is True
