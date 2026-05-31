# Proactive Auto-Hunt — Concept Stub

**Date:** 2026-05-31
**Status:** ⚠️ CONCEPT — NOT yet designed. Brainstorm required before any plan. This file captures the idea and the questions to resolve, not an approved design.

## Idea

Flip HireSense from **pull** (user opens the app and searches) to **push**: a scheduled agent that periodically hunts the freshly-ingested corpus, surfaces the top *new* matches against the profile (now also shaped by the learned taste vector), and optionally **pre-drafts applications** (CV + cover letter from the existing templates) for the user to approve.

## Why it's compelling here

- Leverages everything already built: ingestion (with lifecycle/closure detection), matching + the new taste-vector re-ranking, the CV/cover-letter generation, and tracking.
- Highest *felt* value: the user wakes up to "here are 5 strong new roles, 2 already have draft applications" instead of having to go look.
- Composes naturally with the preference loop — the daily digest is exactly the taste-ranked page 1.

## Rough scope (to be refined by brainstorming)

- A scheduled job (external cron, like the existing revalidation sweep — the system does **not** self-schedule, per [[project_job_lifecycle]]) that: runs after ingestion, computes the top-N new matches since the last run, and produces a digest.
- A "digest" persistence + an API/endpoint the frontend (and/or a notification) reads.
- Optional: auto-generate draft applications for the top matches into the existing application-artifact storage, in a "draft / awaiting approval" state.

## Likely integration points

- Ingestion (new-since-timestamp query), matching/preference (taste-ranked top-N), applications + cover-letter-templates (draft generation), tracking (seed `SAVED` entries?), identity (whose profile).
- Delivery: in-app digest view vs. email/notification (the latter introduces an outbound channel the system doesn't have yet).

## Open questions to resolve in brainstorming

1. **Cadence & trigger** — daily? after each ingestion run? who triggers the cron?
2. **Digest vs. auto-apply** — surface-only first, or include pre-drafted applications? Auto-apply is high-stakes and outward-facing — almost certainly approval-gated, never auto-submitted.
3. **"New since" semantics** — dedupe against what the user has already seen/acted on; interaction with closure detection.
4. **Delivery channel** — in-app only (no new infra) vs. email/push (new outbound capability, secrets, deliverability).
5. **Top-N selection** — pure taste-ranked top-N, or a freshness/diversity blend so the digest isn't the same roles every day?
6. **Single-user assumption** — current system is effectively single-user; does this stay single-user?

## Explicitly undecided

Everything above. Do **not** write an implementation plan from this file — run `superpowers:brainstorming` first to produce an approved design spec, then `writing-plans`.
