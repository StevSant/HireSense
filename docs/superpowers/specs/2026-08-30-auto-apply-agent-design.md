# Auto-Apply Agent — Design (Autopilot Phase 5)

**Date:** 2026-08-30
**Initiative:** [HireSense Autopilot](./2026-06-21-autopilot-initiative.md) — Phase 5
**Status:** Approved for planning
**Composes:** Phase 1 (scheduler), Phase 2 (notifications), Phase 4 (autopilot drafting pipeline),
the `applications` generation + packet services, and the Phase 0 apply-method classification.

## Goal

Make **automatic job application the primary path** through HireSense. On a cadence, the
autopilot pipeline drafts an application, machine-approves it when it passes deterministic
quality checks, and a local browser agent fills and submits the employer's application form
without the candidate present. Manual review becomes the *fallback* for cases the agent
cannot ground with confidence, not the default route for every job.

Reference product: JobCopilot, which submits on the candidate's behalf at volume. HireSense
targets the same outcome using the candidate's own browser session rather than a vendor's
cloud, and with a per-field grounding rule that JobCopilot does not offer.

## Supersedes

This design deliberately reverses two previously shipped commitments. Both source documents
are amended by this spec rather than left standing in contradiction:

1. **`2026-06-14-apply-assist-phase2-extension-handoff.md`** declared *"Prefill + review + user
   clicks Submit. Never headless auto-submit"* as a non-negotiable design principle. That
   principle is **withdrawn for the agent path**. The userscript it describes remains shipped
   and unchanged as the manual fallback.
2. **`2026-08-27-external-workflow-hardening-design.md`** listed *"Automatic submission to job
   portals"* as an explicit non-goal. That non-goal is **removed**.

The risk those documents named is real and unchanged: automated submission puts the
candidate's own board accounts at risk of suspension, and puts their name on documents they
did not read before they went out. The owner has accepted that risk explicitly. This design
therefore does not attempt to eliminate it — it makes it **bounded, observable, and
reversible**: dry-run by default, capped per day, killable without a redeploy, refusing to
answer anything it cannot ground, and recording an audit tape of every field it filled.

## Decisions taken

| Decision | Choice | Rationale |
| --- | --- | --- |
| Execution surface | **Local browser agent** driving the candidate's real Chrome profile over CDP | Reuses sessions already signed in; no credential vault; file uploads work; far fewer bot-blocks than a datacenter IP |
| Channel scope | **All channels, LLM-driven** — ATS forms, account-gated boards, redirects, unknown | Maximum coverage; ATS forms still take a cheap deterministic path first |
| Ambiguity handling | **Confidence gate** — submit above threshold, escalate below | Tunable toward fully unattended as trust grows |
| Approval gate | **Machine approval on quality pass** | The existing `ApplicationPacket` gate is retained intact; only the approver changes |

## Non-goals

- A server-side headless worker with a stored credential vault. The runner seam leaves room
  for one later; it is not built now.
- CAPTCHA solving, 2FA handling, or any bot-detection evasion. These escalate to the human,
  always, regardless of confidence.
- Live-portal smoke tests. Retained from the hardening spec: tests never submit to a real
  employer form.
- Changing `ApplicationStatus`. Submission state lives in the `submission` module; `tracking`
  keeps its six business statuses.
- Replacing the Apply Assist userscript. It stays as the manual fallback.

## Architecture — new `submission/` bounded context

Hexagonal, matching every other module: `api → domain ← infrastructure`, wired in `bootstrap/`.

### `domain/`

- `submission_status.py` — `SubmissionStatus`: `queued`, `claimed`, `in_progress`,
  `escalated`, `submitted`, `failed`, `abandoned`.
- `submission_attempt.py` — `SubmissionAttempt` (pure Pydantic).
- `submission_event.py` — `SubmissionEvent` + `SubmissionEventKind`.
- `page_observation.py` — `PageObservation`, `FormField`.
- `agent_action.py` — the `AgentAction` union: `FillFields`, `ClickAction`, `NavigateAction`,
  `UploadFileAction`, `SubmitAction`, `EscalateAction`, `DoneAction`.
- `field_answer.py` — `FieldAnswer` (selector, canonical_key, value, confidence, source).
- `answer_source.py` — `AnswerSource`: `deterministic_map`, `profile`, `claims`,
  `job_context`, `llm`.
- `form_agent_service.py` — `FormAgentService.next_action(attempt, observation)`.
- `submission_service.py` — the state machine: lease, observe, complete, escalate, resume,
  abandon, daily-cap accounting.
- `grounding.py` — the answer validator (see below).
- `ports/` — `SubmissionRepository`, `FormAnswerPort` (the LLM seam), `ArtifactSourcePort`.

### `infrastructure/`

- `submission_attempt_orm.py`, `submission_event_orm.py` — both registered in
  `infrastructure/registry.py`.
- `submission_repository.py` — extends `SqlRepository`.
- `llm_form_answerer.py` — implements `FormAnswerPort` over the shared `LLMPort` chain.

### `api/`

`provider.py`, `dependencies.py`, `routes.py`, `schemas.py`, all auth-gated:

| Route | Purpose |
| --- | --- |
| `POST /submission/lease` | Runner claims up to N queued attempts |
| `POST /submission/attempts/{id}/observe` | Runner posts a `PageObservation`, receives an `AgentAction` |
| `POST /submission/attempts/{id}/heartbeat` | Lease renewal |
| `POST /submission/attempts/{id}/complete` | Terminal result + evidence |
| `GET /submission/attempts` | List, filterable by status — backs the review queue |
| `GET /submission/attempts/{id}/events` | The audit tape |
| `POST /submission/attempts/{id}/resume` | Human supplies the escalated answers; re-queues |
| `POST /submission/attempts/{id}/abandon` | Give up on this job |
| `POST /submission/enqueue` | Manual enqueue of one application (admin / on-demand) |

## Data model

Two tables, one Alembic revision.

### `submission_attempts`

`id` (UUID pk), `application_id` (indexed), `job_id`, `packet_id`, `channel`, `target_url`,
`status`, `attempt_no`, `escalation_reason`, `escalated_fields` (JSON), `runner_id`,
`claimed_at`, `lease_expires_at`, `evidence` (JSON), `started_at`, `finished_at`,
`created_at`.

A uniqueness guard on `application_id` for non-terminal statuses prevents two live attempts
against the same application.

### `submission_events`

`id`, `attempt_id` (indexed), `seq`, `kind`, `payload` (JSON), `created_at`. Append-only.

**Redaction rule.** PII field values are recorded as `canonical_key` + confidence + a
SHA-256 value hash — never the raw value. Free-text screening answers are stored **in full**,
because those are the sentences that went out under the candidate's name and must be readable
back. This asymmetry is intentional.

## The agent loop

`FormAgentService.next_action(attempt, observation) -> AgentAction` runs a two-tier,
cheap-first resolution over the observation's required fields.

**Tier 1 — deterministic.** Reuses the existing `_LABEL_PATTERNS` / `build_autofill_plan`
from `applications/domain/ats_field_map.py` against each field's visible label. Matches yield
`confidence=1.0`, `source=deterministic_map`. Free, and covers the common identity fields on
nearly every form.

**Tier 2 — LLM.** Only the *residual required* fields reach the model, batched into **one call
per page**, grounded on the candidate profile, their verified `claims`, and the job
description. Routed through the shared `LLMPort` decorator chain
(`UsageTrackingLLMAdapter → FeatureConfiguredLLMAdapter → LangChainLLMAdapter`) so auto-apply
spend appears in `admin` usage tracking alongside every other feature. Each answer carries a
self-scored confidence and a one-line rationale, both persisted as an `llm_decision` event.

### The grounding rule

The model may answer **only** from profile, claims, or job text. A field it cannot ground
returns `confidence=0.0` by construction — it is not permitted to produce a plausible guess.
`grounding.py` enforces this after the fact: any numeric, date, boolean, or credential-shaped
answer that cannot be traced to a profile field or a verified claim is rejected and forced to
zero confidence regardless of what the model claimed.

This is the line between *automatic* and *fabricating credentials under the candidate's name*,
and it is the one invariant in this design that is not tunable by configuration.

### The confidence gate

`min(confidence)` across required fields `>= submission_confidence_threshold` (default `0.75`)
→ `SubmitAction`. Below → `EscalateAction` naming the specific fields. `captcha_detected`,
2FA, or an identity challenge short-circuits to `EscalateAction` unconditionally, before the
gate is consulted.

## Escalation, review, and the learning loop

Escalated attempts surface at `GET /submission/attempts?status=escalated` and via a new
`notifications/domain/submission_escalation_email.py` (alongside the existing
`pipeline_drafts_email.py`).

`POST /submission/attempts/{id}/resume` takes the human's answers for the named fields,
re-queues the attempt — **and writes those answers back to profile prefill / claims, so the
same question never escalates twice.**

That write-back is load-bearing. Without it the confidence gate is a permanent bottleneck and
the product is assisted, not automatic. With it, the escalation queue drains toward empty as
the answer corpus fills, and the system converges on unattended operation. It is what makes
"manual is the fallback" true over time rather than aspirational.

## The runner

A new console script, `apply-agent = "hiresense.runner.cli:main"`. It communicates with the
backend over **HTTP only** and imports nothing from any module's `domain/` — the same
arms-length relationship the userscript has.

Loop per leased attempt:

1. `POST /submission/lease` with `runner_id` and capacity.
2. Connect to the candidate's Chrome over CDP (`apply_agent_cdp_url`, default
   `http://localhost:9222`).
3. Navigate to `target_url` (the job's `preferred_apply_url`).
4. Serialize the DOM into a `PageObservation`.
5. `POST /observe` → execute the returned `AgentAction` → repeat, to `apply_agent_max_steps`
   (default 25).
6. For `UploadFileAction`, fetch `/applications/{id}/cv.pdf` and `/cover-letter.pdf` to temp
   files and attach via `set_input_files` — the capability the userscript structurally lacks.
7. `POST /complete` with evidence: final URL, confirmation text snippet, screenshot hash.
8. Heartbeat renews the lease throughout.

**Lease semantics.** A crashed or killed runner's lease expires and the attempt returns to
`queued`, capped at `submission_max_attempts` (default 2). A hung browser therefore neither
silently eats a job nor double-submits one.

**The DOM serializer is a security boundary, not a convenience.** Job pages are untrusted
content, and the hardening spec's commitment that "ingestion and LLM content are data, never
executable instructions" applies unchanged here. The serializer strips scripts, styles, and
comments, truncates text nodes, and the resulting observation enters the prompt inside a
delimited data block.

## Autopilot wiring (Phase 5)

`AutopilotPipelineService` gains an optional injected `submission_enqueuer`. After a draft
reaches `DraftStatus.DRAFTED` — not `PARTIAL`, not `FAILED`:

1. `packet_service.create(application_id)`
2. If `packet.quality_report.ready` **and** the match score `>= autopilot_submit_min_score`
   → `packet_service.approve(packet.id)`. This is the machine approval.
3. `enqueuer.enqueue(application_id, packet_id)`, subject to the daily cap.

Otherwise the reason is recorded and the draft stays for manual review.

**`ApplyService.mark_applied` is not modified.** The completion path calls it and it passes,
because the packet is genuinely `approved` and genuinely `is_current()`. The gate keeps its
stale-artifact protection in full; only the identity of the approver changes. Machine
approval slots *into* the existing gate rather than around it.

## Configuration — new `config/groups/submission.py`

| Setting | Default | Purpose |
| --- | --- | --- |
| `autopilot_submit_enabled` | `False` | Master switch for the whole outbound path |
| `autopilot_submit_min_score` | `0.75` | Match score floor for machine approval |
| `autopilot_submit_daily_cap` | `10` | Attempts enqueued per calendar day |
| `submission_confidence_threshold` | `0.75` | The confidence gate |
| `submission_max_attempts` | `2` | Retries after a lease expiry |
| `submission_lease_seconds` | `300` | Lease duration |
| `apply_agent_cdp_url` | `http://localhost:9222` | Chrome remote-debugging endpoint |
| `apply_agent_api_base` | `http://localhost:8000` | Backend base URL for the runner |
| `apply_agent_api_token` | `""` (SecretStr) | Runner auth token |
| `apply_agent_max_steps` | `25` | Step ceiling per attempt |
| `apply_agent_dry_run` | `True` | Do everything **except** the final click |

All mirrored into `.env.example` with comments, per the project's no-hardcoded-values rule.

`apply_agent_dry_run` ships **on**: the agent fills every field, resolves every question, and
captures evidence, but stops short of submitting. The candidate watches a few runs, reads the
audit tape, and then turns it off. Shipping an auto-submitter armed on first boot would be
indefensible.

A `job_toggles` row additionally allows killing the scheduled path from the admin UI without a
redeploy, layered on top of the config flag exactly as the other scheduler jobs are.

## Testing

**Unit** — deterministic/residual split; threshold boundary conditions; CAPTCHA short-circuit;
grounding validator rejecting ungrounded numeric/date/boolean answers; state machine
transitions; lease expiry and requeue; `max_attempts` exhaustion; daily cap; machine-approval
rule including the `PARTIAL`-draft exclusion.

**Integration** (SQLite, no Postgres, per existing convention) — the full `/submission` route
surface; the autopilot enqueue path end to end; resume-with-answers persisting back to profile.

**Runner** — the browser driver faked; a saved Greenhouse HTML fixture drives the serializer
and the loop with no live browser.

**No live-portal tests.** Retained unchanged from the hardening spec.

Playwright is added as an **optional dependency group**, so the Docker image and CI runtime are
untouched by this work.

## Rollout

1. Ship with `autopilot_submit_enabled=False`. Nothing changes for anyone.
2. Enable with `apply_agent_dry_run=True`. Review the audit tape for a handful of jobs.
3. Turn dry-run off with `autopilot_submit_daily_cap=1..3`. Verify real confirmations.
4. Raise the cap; tune `submission_confidence_threshold` down as the escalation queue proves
   it is answering well.
