from __future__ import annotations

import logging
import statistics
from typing import Any

from pydantic import BaseModel

from hiresense.ingestion.domain.seniority import SeniorityLevel, detect_seniority

logger = logging.getLogger(__name__)


class SeniorityBand(BaseModel):
    level: str
    median_annual: int
    sample_size: int


class CompBenchmark(BaseModel):
    """Profile-aware compensation benchmark.

    The market band (p25/median/p75) is computed from the salaries of the jobs
    that best match the candidate's profile (ANN over the corpus). `by_seniority`
    splits those matches by detected seniority; `your_median_annual` is the
    candidate's tracked-application median for an above/below-market read; the
    suggested ask range is [median, p75] of the market band.
    """

    insufficient_data: bool
    currency: str | None = None
    p25_annual: int | None = None
    median_annual: int | None = None
    p75_annual: int | None = None
    sample_size: int = 0
    by_seniority: list[SeniorityBand] = []
    your_median_annual: int | None = None
    your_sample_size: int = 0
    ask_min_annual: int | None = None
    ask_max_annual: int | None = None


def _percentile(sorted_vals: list[int], q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, max(0, round(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


_SENIORITY_ORDER = [
    SeniorityLevel.INTERN, SeniorityLevel.JUNIOR, SeniorityLevel.MID,
    SeniorityLevel.SENIOR, SeniorityLevel.LEAD,
]


class CompBenchmarkService:
    def __init__(
        self, *, embedding: Any, vector_store: Any, corpus: Any, salary_parser: Any,
        tracking_read: Any, top_k: int, min_sample: int,
    ) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._corpus = corpus
        self._salary = salary_parser
        self._tracking = tracking_read
        self._top_k = top_k
        self._min_sample = min_sample

    async def compute(self, *, profile_skills: list[str], summary: str) -> CompBenchmark:
        text = f"{' '.join(profile_skills)}\n{summary}".strip()
        if self._vector_store is None or not text:
            return CompBenchmark(insufficient_data=True)
        try:
            vectors = await self._embedding.embed([text])
            results = await self._vector_store.search(vectors[0], top_k=self._top_k)
        except Exception:
            logger.exception("comp-benchmark: embedding/search failed")
            return CompBenchmark(insufficient_data=True)

        ids = [r.id for r in results]
        rows = self._corpus.rows_for_ids(ids)
        descriptions = self._corpus.descriptions_for_ids(ids)

        # mid-point annual salary per matched job, grouped by currency
        by_currency: dict[str, list[tuple[str, int]]] = {}  # currency -> [(job_id, mid)]
        for jid, row in rows.items():
            parsed = self._salary.parse(row.salary_range)
            if parsed is None:
                continue
            mid = (parsed.min_annual + parsed.max_annual) // 2
            by_currency.setdefault(parsed.currency, []).append((jid, mid))

        if not by_currency:
            return CompBenchmark(insufficient_data=True)

        dominant = max(by_currency, key=lambda c: len(by_currency[c]))
        entries = by_currency[dominant]
        vals = sorted(mid for _, mid in entries)
        your_median, your_n = self._pipeline_median(dominant)

        if len(vals) < self._min_sample:
            return CompBenchmark(
                insufficient_data=True, currency=dominant, sample_size=len(vals),
                your_median_annual=your_median, your_sample_size=your_n,
            )

        median = int(statistics.median(vals))
        p75 = _percentile(vals, 0.75)
        return CompBenchmark(
            insufficient_data=False, currency=dominant,
            p25_annual=_percentile(vals, 0.25), median_annual=median, p75_annual=p75,
            sample_size=len(vals),
            by_seniority=self._seniority_bands(entries, rows, descriptions),
            your_median_annual=your_median, your_sample_size=your_n,
            ask_min_annual=median, ask_max_annual=p75,
        )

    def _seniority_bands(
        self, entries: list[tuple[str, int]], rows: dict, descriptions: dict,
    ) -> list[SeniorityBand]:
        buckets: dict[SeniorityLevel, list[int]] = {}
        for jid, mid in entries:
            row = rows.get(jid)
            if row is None:
                continue
            level = detect_seniority(row.title, descriptions.get(jid, ""))
            if level is SeniorityLevel.UNKNOWN:
                continue
            buckets.setdefault(level, []).append(mid)
        bands: list[SeniorityBand] = []
        for level in _SENIORITY_ORDER:
            mids = buckets.get(level)
            if mids and len(mids) >= self._min_sample:
                bands.append(SeniorityBand(
                    level=level.value, median_annual=int(statistics.median(mids)),
                    sample_size=len(mids),
                ))
        return bands

    def _pipeline_median(self, currency: str) -> tuple[int | None, int]:
        """Median annual salary across the candidate's tracked applications, in
        the same currency as the market band. None when none are parseable."""
        if self._tracking is None:
            return None, 0
        try:
            apps = self._tracking.list()
        except Exception:
            logger.exception("comp-benchmark: tracking list failed")
            return None, 0
        job_ids = [str(a.job_id) for a in apps if getattr(a, "job_id", None)]
        if not job_ids:
            return None, 0
        salary_by_id = self._corpus.salary_strings_for_ids(job_ids)
        mids: list[int] = []
        for raw in salary_by_id.values():
            parsed = self._salary.parse(raw)
            if parsed is not None and parsed.currency == currency:
                mids.append((parsed.min_annual + parsed.max_annual) // 2)
        if not mids:
            return None, 0
        return int(statistics.median(mids)), len(mids)
