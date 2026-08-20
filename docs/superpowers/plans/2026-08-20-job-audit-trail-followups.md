# Job audit trail — remaining follow-ups

**Date:** 2026-08-20
**Status:** Feature shipped; these are the items deliberately deferred.

The per-job audit trail (spec `2026-08-19-job-audit-trail-design.md`, plan
`2026-08-19-job-audit-trail.md`) shipped in 18 commits. Its final whole-branch review raised
4 Important findings, all fixed before merge, plus the Minors below, which were reviewed and
consciously parked. They are recorded here rather than lost with the scratch workspace.

## Parked minor findings


1. **Run detail truncates silently.** `api/routes.py:329` defaults `limit=200`
   while a run legitimately produces ~1,140 events. The runs page never passes a
   limit (`ingestion.service.ts:129`), so a row whose summary reads "713 inserted"
   expands to 200 rows with nothing saying the list is partial.
2. **Runs page has no pagination.** `listRuns()` is called with no arguments
   (`runs.component.ts:71`) → 25 most recent runs, and `offset` is plumbed through
   the service but unreachable from the UI. Combined with I3 the older history
   becomes permanently unviewable.
3. **`run_id` is dropped on read.** `JobHistoryEvent` has no `run_id` field, so
   `_to_domain` (`job_history_repository.py:16`) discards it. The per-job timeline
   cannot link an event to the run that produced it — run→jobs works, jobs→run
   does not. `reason` still separates the two closure paths, so this is a
   navigation gap, not a correctness one.
4. **A failed `start_run` silently degrades a whole pass.**
   `job_history_recorder.py:41-46` returns `None` on failure and the pass proceeds,
   writing every event with `run_id=NULL`. Those closures then read as sweep
   closures on any run-scoped query (`reason` still disambiguates). Worth a WARNING
   at the orchestrator call site.
5. **`sa.JSON()` rather than JSONB.** `046_create_job_history_events.py:26`; the
   spec specified `jsonb`. Nothing queries inside the column today, so this only
   costs re-parsing on read and forecloses GIN indexing later.
6. **Timeline `@for` track key can collide.**
   `job-history-timeline.component.html:14` tracks on `occurred_at + event`. Two
   events of the same type for one job at the same timestamp would raise Angular's
   duplicate-key error. Not reachable through current write paths (one event per
   job per batch), but an index- or id-based key is safer.
7. **One bad row loses a whole source's batch.** `insert_events` is a single
   executemany (`job_history_repository.py:59`); any constraint violation — e.g. a
   job hard-deleted by `_prune_jobs` between `bulk_upsert` and `record_outcomes` —
   discards every event for that source, swallowed, visible only as one
   `automation_failures_total` increment. Acceptable given the design's stated
   non-atomicity, but worth an alert on that metric.
8. **`TRIGGER_LABELS` covers two of the schema's three values.**
   `runs.component.ts:19-22` maps `fetch` and `scheduler`; `manual` renders as
   "Unknown trigger". Correct today — the plan deliberately narrowed the trigger
   vocabulary to two and no caller emits `manual` — and the fallback is safe.
   Flagged only so the coupling is on record.


## Triage of minors carried from per-task reviews


None block merge.

| Deferred item | Verdict |
|---|---|
| Duplicated test fakes across the ingestion unit tests | Do not fix now. A `conftest.py` for `tests/unit/ingestion/` is worth doing, but as its own cleanup — folding it in adds churn to files four tasks touched. |
| `finish_run` on an unknown run id untested | Do not fix now. Behaviour is correct and one line; the test is nice-to-have. |
| `_counts_for` key hint `dict[Any, ...]` | Do not fix now. Cosmetic, and `Any` also absorbs the SQLite-vs-PostgreSQL UUID representation difference, so tightening it needs care. |
| `provider.py`/`dependencies.py` import from the implementation module | Do not fix. Matches the pre-existing style of both files; changing only the new lines would make them less consistent. |
| No test for `/runs` offset pagination | Do not fix now — but see Minor 2: no UI exercises offset either, so the untested parameter is currently unreachable. Fix the two together. |
| Diff computed then discarded on REOPENED | Do not fix. See below. |

# The two design decisions

**REOPENED records an empty diff — right call, with a caveat.** The reopen is the
event a reader cares about, and the current design loses nothing permanently: the
next content change re-records the fields, and no migration is needed to widen it
later. The caveat is that a reopen-with-changes is genuinely more interesting than
a plain reopen — a listing that comes back with a different salary is exactly the
"is this the same job or a new one?" question the spec opens with. Since
`_apply_to_row` already computes the diff on that path and throws it away
(`jobs_repository.py:139`), attaching it costs one line and no schema change. I
would attach it, but I would not block on it.

**No synthetic backfill — right call, unreservedly.** An audit trail that
fabricates events it did not witness is worse than one with a known start date,
and the empty-state wording is the honest presentation. The only thing that makes
it currently wrong is I1: the wording claims a job predates the trail when the
real reason is that its bucket was never wired. Fix I1 and the decision stands
cleanly.

## Scope deliberately excluded from the original plan

- **Per-source counts on run detail.** The spec's API section promised them, but
  `job_history_events` has no `source` column, so they would need either denormalising
  `source` onto each event or joining `ingested_jobs`. Run detail ships per-event-type totals
  only. Deciding the denormalisation question is the follow-up.
- **No backfill for pre-existing jobs.** Per the spec's resolved open question, jobs that
  predate the feature get no synthetic `inserted` events; the timeline empty state says the
  audit trail begins 19 Aug 2026 rather than implying nothing happened.
- **A `conftest.py` for `tests/unit/ingestion/`.** Test fakes are currently duplicated between
  `test_orchestrator.py`/`test_orchestrator_history.py` and
  `test_job_revalidation_service.py`/`test_revalidation_history.py`, because no shared fixture
  module exists. Extracting one was out of scope for every task that noticed it.
