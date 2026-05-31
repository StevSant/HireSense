# Analytics & Market Insight — Concept Stub

**Date:** 2026-05-31
**Status:** ⚠️ CONCEPT — NOT yet designed. Brainstorm required before any plan. Captures the idea and open questions only.

## Idea

Two related analytics surfaces mined from data HireSense already has:

1. **Funnel metrics** — the user's own pipeline: application → response → interview → offer rates, time-in-stage, conversion by source/company, derived from the `tracking` status history.
2. **Market intelligence** — aggregate signal from the ingested corpus: in-demand skills, salary ranges/trends, remote vs. on-site mix, and a **skill-gap** view comparing the profile against what the market is asking for.

## Why it's compelling here

- Pure leverage of existing data: the tracking pipeline already records outcomes; ingestion already holds a large, normalized job corpus with skills/compensation/seniority.
- The skill-gap view closes a loop with matching: "the market wants X, your profile is light on X" is directly actionable (and could feed profile/CV optimization).

## Rough scope (to be refined by brainstorming)

- **Funnel**: aggregate tracking statuses into conversion rates + time-in-stage; slice by source/company/date.
- **Market**: aggregate corpus fields (skills frequency, salary distribution, seniority/remote mix); trend over ingestion time.
- **Skill gap**: diff profile skills vs. top in-demand corpus skills (semantic, not just literal — embeddings already available).
- Surfaces: a dashboard page (the frontend already has a `dashboard` route) + supporting read endpoints.

## Likely integration points

- `tracking` (status history — may need timestamps per transition, which today's model doesn't fully store — see open questions), `ingestion` (corpus aggregation queries), `profile` + embeddings (skill-gap), the `dashboard` frontend page.

## Open questions to resolve in brainstorming

1. **Funnel data sufficiency** — `TrackedApplication` stores current `status` + `applied_at`, but not a full per-transition timestamp history. Time-in-stage / conversion-over-time may require a status-history table (relates to the Phase 2 `TrackingStatusChangedEvent` — could persist transitions). Decide the data model first.
2. **Market aggregation cost** — compute on the fly vs. a periodic materialized rollup (and where the cron lives, given no self-scheduling).
3. **Skill-gap method** — literal skill set diff vs. embedding-based semantic gap; how to rank "most worth learning."
4. **Single-user scope** — funnel is inherently per-user; fine for the current single-user system.
5. **Privacy/aggregation** — market stats are derived from public postings; no concern. Funnel is personal; stays local.

## Explicitly undecided

All of the above. Run `superpowers:brainstorming` before planning. Note the dependency: meaningful funnel analytics likely wants the per-transition history that Phase 2's tracking event could persist — sequence accordingly.
