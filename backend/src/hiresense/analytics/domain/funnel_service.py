from __future__ import annotations

import logging
import statistics
import uuid as uuid_mod
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_STAGES = ["saved", "applied", "interviewing", "offered", "accepted"]
_RANK = {s: i for i, s in enumerate(_STAGES)}


class FunnelStage(BaseModel):
    stage: str
    reached: int
    conversion_from_prev: float | None
    median_days_in_stage: float | None
    current: int


class SourceOutcome(BaseModel):
    """Per job-source pipeline outcome: how many tracked apps came from this
    source and what share reached the interview stage (by current status)."""

    source: str
    applications: int
    reached_interview: int
    interview_rate: float


class FunnelMetrics(BaseModel):
    stages: list[FunnelStage]
    rejected: int
    current_rejected: int
    total_applications: int
    by_source: list[SourceOutcome] = []


class FunnelService:
    def __init__(self, history: Any, applications_read: Any = None, corpus: Any = None) -> None:
        self._history = history
        self._applications = applications_read
        self._corpus = corpus

    def compute(self) -> FunnelMetrics:
        rows = self._history.list_history()
        by_app: dict[uuid_mod.UUID, list] = defaultdict(list)
        for r in rows:
            by_app[r.application_id].append(r)

        reached = {s: 0 for s in _STAGES}
        current = {s: 0 for s in _STAGES}
        rejected = 0
        current_rejected = 0

        for app_rows in by_app.values():
            app_rows = sorted(app_rows, key=lambda r: (r.changed_at, _RANK.get(r.to_status, 99)))
            to_statuses = [r.to_status for r in app_rows]
            # high-water mark across non-terminal stages
            max_rank = -1
            for r in app_rows:
                if r.to_status in _RANK:
                    max_rank = max(max_rank, _RANK[r.to_status])
            for s in _STAGES:
                if max_rank >= _RANK[s]:
                    reached[s] += 1
            if "rejected" in to_statuses:
                rejected += 1
            # current status = the last row's to_status
            last = to_statuses[-1]
            if last in current:
                current[last] += 1
            elif last == "rejected":
                current_rejected += 1

        # time-in-stage: for apps that entered both stage N and N+1, the gap.
        stages_out: list[FunnelStage] = []
        for i, s in enumerate(_STAGES):
            conv: float | None = None
            if i > 0:
                prev = reached[_STAGES[i - 1]]
                conv = round(reached[s] / prev, 4) if prev else None
            # median time spent in stage s = median(entry[s+1] - entry[s]) over apps with both
            median_days: float | None = None
            if i + 1 < len(_STAGES):
                nxt = _STAGES[i + 1]
                gaps = []
                for app_rows in by_app.values():
                    entered: dict[str, float] = {}
                    for r in sorted(app_rows, key=lambda r: r.changed_at):
                        if r.to_status in _RANK:
                            entered.setdefault(r.to_status, r.changed_at.timestamp() / 86400.0)
                    if s in entered and nxt in entered:
                        gaps.append(entered[nxt] - entered[s])
                if gaps:
                    median_days = round(statistics.median(gaps), 2)
            stages_out.append(
                FunnelStage(
                    stage=s,
                    reached=reached[s],
                    conversion_from_prev=conv,
                    median_days_in_stage=median_days,
                    current=current[s],
                )
            )
        return FunnelMetrics(
            stages=stages_out,
            rejected=rejected,
            current_rejected=current_rejected,
            total_applications=len(by_app),
            by_source=self._by_source(),
        )

    def _by_source(self) -> list[SourceOutcome]:
        """Outcomes grouped by the job's source. Uses each tracked app's current
        status (rank >= interviewing counts as reached-interview) — a simple
        which-source-converts signal, not a high-water-mark over history."""
        if self._applications is None or self._corpus is None:
            return []
        try:
            apps = self._applications.list()
        except Exception:
            logger.exception("funnel: applications lookup failed — omitting by-source outcomes")
            return []
        job_ids = [str(a.job_id) for a in apps if getattr(a, "job_id", None)]
        if not job_ids:
            return []
        rows = self._corpus.rows_for_ids(job_ids)
        totals: dict[str, int] = defaultdict(int)
        reached: dict[str, int] = defaultdict(int)
        for app in apps:
            jid = str(app.job_id) if getattr(app, "job_id", None) else None
            row = rows.get(jid) if jid else None
            if row is None or not row.source:
                continue
            totals[row.source] += 1
            if _RANK.get(app.status, -1) >= _RANK["interviewing"]:
                reached[row.source] += 1
        outcomes = [
            SourceOutcome(
                source=src,
                applications=n,
                reached_interview=reached[src],
                interview_rate=round(reached[src] / n, 4) if n else 0.0,
            )
            for src, n in totals.items()
        ]
        outcomes.sort(key=lambda o: (o.applications, o.interview_rate), reverse=True)
        return outcomes
