"""One-off: re-fetch ONLY getonboard so company names get resolved + persisted.

The getonboard company *id* was never stored, so the blank-company rows can only
be fixed by re-pulling from the API (the adapter resolves names via
/companies/{id} and the upsert persists them). We limit the orchestrator to the
getonboard source and disable the inline quality classifier (re-run
scripts/backfill_job_quality.py afterward, which classifies with bounded
concurrency) to avoid firing ~N/20 concurrent LLM calls on the touched set.

Run from backend/:  uv run python scripts/refetch_getonboard.py
"""

from __future__ import annotations

import asyncio

from hiresense.main import create_app


async def main() -> None:
    app = create_app()
    orchestrator = app.state.ingestion.get_orchestrator()

    sources = [s for s in orchestrator._sources if s.source_name() == "getonboard"]  # noqa: SLF001
    if not sources:
        print("getonboard source not enabled; nothing to do.")
        return
    orchestrator._sources = sources  # noqa: SLF001
    orchestrator._quality_classifier = None  # noqa: SLF001  (reclassify via backfill)
    orchestrator._last_run_at = 0.0  # noqa: SLF001  (fresh process, skip cooldown)

    print("Re-fetching getonboard (resolving company names)...")
    new_jobs = await orchestrator.run()
    print(f"Done. {len(new_jobs)} new job(s) inserted; existing rows updated in place.")


if __name__ == "__main__":
    asyncio.run(main())
