"""One-off backfill: classify quality/spam for the existing boards corpus.

Quality is computed at ingestion going forward, but jobs already stored before
the feature shipped are all "ok". This re-runs the real (LLM-backed) classifier
over the stored corpus and persists verdicts so the "Show low-quality" filter
takes effect immediately, without an external re-fetch.

Run from backend/:  uv run python -m scripts.backfill_job_quality

Concurrency is bounded by processing in sequential slices (the classifier itself
gathers its per-20 chunks concurrently, so a whole-corpus call would otherwise
fire ~N/20 LLM requests at once).
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter

# Import the app factory first so the package graph initialises in the right
# order (importing the ports submodule directly first triggers a circular import
# via portal_scanner).
from hiresense.main import create_app
from hiresense.ingestion.ports.jobs_repository import QualityUpdate

SLICE = 60  # jobs per classify() call → ~3 concurrent LLM chunks at a time


async def main() -> None:
    app = create_app()
    orchestrator = app.state.ingestion.get_orchestrator()
    classifier = orchestrator._quality_classifier  # noqa: SLF001 (one-off ops script)
    repository = orchestrator._repository  # noqa: SLF001

    if classifier is None:
        print("No quality classifier wired; nothing to do.")
        return

    jobs = repository.list_all()
    # Optional source filter: `... backfill_job_quality.py getonboard` reclassifies
    # just that source (e.g. after a re-fetch resolved its company names).
    source_filter = sys.argv[1] if len(sys.argv) > 1 else None
    if source_filter:
        jobs = [j for j in jobs if j.source == source_filter]
    print(f"Classifying {len(jobs)} {source_filter or 'boards'} jobs in slices of {SLICE}...")

    tally: Counter[str] = Counter()
    flagged: list[tuple[str, str, str]] = []
    for start in range(0, len(jobs), SLICE):
        chunk = jobs[start : start + SLICE]
        verdicts = await classifier.classify(chunk)
        updates = [QualityUpdate(v.job_id, v.quality.value, v.reason) for v in verdicts.values()]
        repository.bulk_update_quality(updates)
        for v in verdicts.values():
            tally[v.quality.value] += 1
            if v.quality.value != "ok":
                job = next((j for j in chunk if j.id == v.job_id), None)
                title = job.title if job else v.job_id
                flagged.append((v.quality.value, title, v.reason or ""))
        print(f"  {min(start + SLICE, len(jobs))}/{len(jobs)} done", flush=True)

    print("\nQuality distribution:", dict(tally))
    print(f"\nFlagged {len(flagged)} jobs:")
    for quality, title, reason in flagged[:50]:
        print(f"  [{quality}] {title[:70]} — {reason[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
