from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FocusItem(BaseModel):
    label: str
    count: int
    avg_score: float


class SearchFocus(BaseModel):
    """Profile-aware "where to aim" view, computed from the candidate's
    best-matching open jobs (ANN over the corpus, spam/closed excluded)."""

    insufficient_data: bool
    match_count: int = 0
    best_fit_companies: list[FocusItem] = []
    best_fit_roles: list[FocusItem] = []
    remote_share: float | None = None
    top_locations: list[FocusItem] = []
    fresh_fit_count: int = 0
    fresh_days: int = 0


def _normalize_title(title: str) -> str:
    """Light role normalisation: strip seniority words / parentheticals / levels
    so 'Senior Backend Engineer (Remote)' and 'Backend Engineer' group together."""
    import re

    t = title.lower()
    t = re.sub(r"\(.*?\)", " ", t)  # drop parentheticals
    t = re.sub(
        r"\b(senior|sr|junior|jr|staff|lead|principal|mid|intern|entry[- ]level|"
        r"i{1,3}|iv|v|[0-9]+)\b",
        " ",
        t,
    )
    t = re.sub(r"[^a-z ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.title() if t else (title.strip() or "—")


def _top(counter: dict[str, list[float]], n: int) -> list[FocusItem]:
    items = [
        FocusItem(label=label, count=len(scores), avg_score=round(sum(scores) / len(scores), 4))
        for label, scores in counter.items()
        if scores
    ]
    items.sort(key=lambda i: (i.count, i.avg_score), reverse=True)
    return items[:n]


class SearchFocusService:
    def __init__(
        self,
        *,
        embedding: Any,
        vector_store: Any,
        corpus: Any,
        top_k: int,
        fresh_days: int,
        top_n: int = 8,
    ) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._corpus = corpus
        self._top_k = top_k
        self._fresh_days = fresh_days
        self._top_n = top_n

    async def compute(self, *, profile_skills: list[str], summary: str) -> SearchFocus:
        text = f"{' '.join(profile_skills)}\n{summary}".strip()
        if self._vector_store is None or not text:
            return SearchFocus(insufficient_data=True)
        try:
            vectors = await self._embedding.embed([text])
            results = await self._vector_store.search(vectors[0], top_k=self._top_k)
        except Exception:
            logger.exception("search-focus: embedding/search failed")
            return SearchFocus(insufficient_data=True)

        score_by_id = {r.id: r.score for r in results}
        rows = self._corpus.rows_for_ids(list(score_by_id))
        # Only genuinely-applyable matches: open + not spam/low-quality.
        matches = [
            (row, score_by_id.get(jid, 0.0))
            for jid, row in rows.items()
            if row.status != "closed" and (row.quality or "ok") == "ok"
        ]
        if not matches:
            return SearchFocus(insufficient_data=True)

        companies: dict[str, list[float]] = defaultdict(list)
        roles: dict[str, list[float]] = defaultdict(list)
        locations: dict[str, list[float]] = defaultdict(list)
        remote = 0
        fresh = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._fresh_days)
        for row, score in matches:
            if row.company.strip():
                companies[row.company.strip()].append(score)
            roles[_normalize_title(row.title)].append(score)
            if row.location.strip():
                locations[row.location.strip()].append(score)
            if row.remote_modality == "remote":
                remote += 1
            if row.posted_date is not None:
                posted = row.posted_date
                if posted.tzinfo is None:
                    posted = posted.replace(tzinfo=timezone.utc)
                if posted >= cutoff:
                    fresh += 1

        return SearchFocus(
            insufficient_data=False,
            match_count=len(matches),
            best_fit_companies=_top(companies, self._top_n),
            best_fit_roles=_top(roles, self._top_n),
            remote_share=round(remote / len(matches), 4),
            top_locations=_top(locations, self._top_n),
            fresh_fit_count=fresh,
            fresh_days=self._fresh_days,
        )
