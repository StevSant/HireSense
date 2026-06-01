from __future__ import annotations

import statistics
import uuid as uuid_mod
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

_STAGES = ["saved", "applied", "interviewing", "offered", "accepted"]
_RANK = {s: i for i, s in enumerate(_STAGES)}


class FunnelStage(BaseModel):
    stage: str
    reached: int
    conversion_from_prev: float | None
    median_days_in_stage: float | None
    current: int


class FunnelMetrics(BaseModel):
    stages: list[FunnelStage]
    rejected: int
    total_applications: int


class FunnelService:
    def __init__(self, history: Any) -> None:
        self._history = history

    def compute(self) -> FunnelMetrics:
        rows = self._history.list_history()
        by_app: dict[uuid_mod.UUID, list] = defaultdict(list)
        for r in rows:
            by_app[r.application_id].append(r)

        reached = {s: 0 for s in _STAGES}
        current = {s: 0 for s in _STAGES}
        rejected = 0

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
                    stage=s, reached=reached[s], conversion_from_prev=conv,
                    median_days_in_stage=median_days, current=current[s],
                )
            )
        return FunnelMetrics(stages=stages_out, rejected=rejected, total_applications=len(by_app))
