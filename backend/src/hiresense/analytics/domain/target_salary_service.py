from __future__ import annotations

import logging
import statistics
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TargetSalary(BaseModel):
    insufficient_data: bool
    currency: str | None = None
    p25_annual: int | None = None
    median_annual: int | None = None
    p75_annual: int | None = None
    sample_size: int = 0


def _percentile(sorted_vals: list[int], q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, max(0, round(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


class TargetSalaryService:
    def __init__(
        self,
        *,
        embedding: Any,
        vector_store: Any,
        corpus: Any,
        salary_parser: Any,
        top_k: int,
        min_sample: int,
    ) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._corpus = corpus
        self._salary = salary_parser
        self._top_k = top_k
        self._min_sample = min_sample

    async def compute(self, *, profile_skills: list[str], summary: str) -> TargetSalary:
        text = f"{' '.join(profile_skills)}\n{summary}".strip()
        if self._vector_store is None or not text:
            return TargetSalary(insufficient_data=True)
        try:
            vectors = await self._embedding.embed([text])
            results = await self._vector_store.search(vectors[0], top_k=self._top_k)
        except Exception:
            logger.exception("target-salary: embedding/search failed")
            return TargetSalary(insufficient_data=True)
        ids = [r.id for r in results]
        salary_by_id = self._corpus.salary_strings_for_ids(ids)
        by_currency: dict[str, list[int]] = {}
        for raw in salary_by_id.values():
            parsed = self._salary.parse(raw)
            if parsed is None:
                continue
            mid = (parsed.min_annual + parsed.max_annual) // 2
            by_currency.setdefault(parsed.currency, []).append(mid)
        if not by_currency:
            return TargetSalary(insufficient_data=True)
        dominant = max(by_currency, key=lambda c: len(by_currency[c]))
        vals = sorted(by_currency[dominant])
        if len(vals) < self._min_sample:
            return TargetSalary(insufficient_data=True, currency=dominant, sample_size=len(vals))
        return TargetSalary(
            insufficient_data=False,
            currency=dominant,
            p25_annual=_percentile(vals, 0.25),
            median_annual=int(statistics.median(vals)),
            p75_annual=_percentile(vals, 0.75),
            sample_size=len(vals),
        )
