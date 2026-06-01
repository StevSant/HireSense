# Outreach & Networking — Design

**Date:** 2026-05-31
**Status:** Design proposed — supersedes the concept stub [2026-05-31-outreach-networking-concept.md](2026-05-31-outreach-networking-concept.md). Brainstormed and approved; pending its own implementation plan.
**Depends on:** profile (candidate name/summary/skills), research (cached company research), tracking (applications + status), the tracked-LLM factory, the style-guide doc `docs/reference/message_To_apprach_recruiters.md`, and the external-cron trigger pattern.

## Problem

HireSense covers ingest → match → apply → track → interview, but nothing helps with **reaching out**: drafting recruiter / hiring-manager messages in the user's voice, recording that outreach happened, and nudging follow-ups when a contacted role goes quiet. The repo already encodes the user's outreach voice (`docs/reference/message_To_apprach_recruiters.md`), and the company-research + profile contexts provide grounding.

## Goals

1. **Generate** an on-brand outreach message for a tracked application, grounded in the profile + (cached) company research + the style-guide doc.
2. **Record** outreach as append-only events on the application (sent / followed-up / replied), copy-only — the user sends manually.
3. **Nudge** follow-ups: an external-cron sweep surfaces applications messaged ≥ N days ago with no progress.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | **Full loop** — generate → record → nudge — but **copy-only** (no outbound send). |
| Contact model | **Anchor outreach to a tracked application** + an optional free-text `contact_name`/`channel` on each event. **No first-class contacts entity** (future). |
| Grounding | profile (name/summary/skills) + **cached** company research (`research.get`, never force-generates) + job context + the style guide. |
| Style guide | **Read the doc at generation time** (path from settings) and inject verbatim; built-in default voice if the file is missing. Editing the markdown changes the voice with no code change. |
| Follow-up | External-cron `POST /outreach/nudge`; stateless sweep keyed on each application's **latest** outreach event + tracking status. |
| Code location | New `outreach` bounded context consuming profile/research/tracking; mirrors analytics/autohunt. |

## Architecture

### 1. Data model (`outreach` context)

New table **`outreach_events`** — append-only log per application (mirrors `application_status_history`):

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `application_id` | UUID, indexed | the tracked application |
| `kind` | varchar(16) | `sent` \| `followed_up` \| `replied` |
| `contact_name` | varchar(255), nullable | optional recipient ("[Name]") |
| `channel` | varchar(32), nullable | optional free-text (`linkedin`, `email`, …) |
| `message` | text, nullable | body for `sent`/`followed_up`; null for a bare `replied` mark |
| `created_at` | timestamptz, default now() (+ Python-side microsecond default) | when recorded |

- Append-only; **generation records nothing** — the user records `sent` after actually sending.
- **Python-side `default=lambda: datetime.now(timezone.utc)`** on `created_at` alongside `server_default=func.now()` (microsecond precision so `latest_for` ordering is deterministic on SQLite — same fix applied to digests).
- Domain: `OutreachEventKind` enum; `OutreachEvent{id, application_id, kind, contact_name?, channel?, message?, created_at}` (one class per file); `OutreachNudge{application_id, company, contact_name?, sent_at, days_since}` (computed read model, not persisted).
- Repository (preference/autohunt pattern) + port: `add(event)`, `list_for(application_id)`, `latest_for(application_id)`, `latest_per_application() -> list[OutreachEvent]`. Alembic migration `019`.

### 2. Generation — `OutreachMessageGenerator` (pure LLM unit, mirrors `CoverLetterGenerator`)

```
generate(*, company, title, job_description, candidate_name, candidate_summary,
         candidate_skills, company_research: str | None, contact_name: str | None,
         style_guide: str, channel: str | None, max_chars: int) -> str
```

- **System prompt:** drafts short, on-brand recruiter/hiring-manager outreach — concise, specific, genuine; no fluff/placeholders/markdown; return only the body, ready to paste.
- **User prompt** injects: the **style guide verbatim** (the strongest voice signal), role (title/company), trimmed job description, candidate name + summary + a few skills, a one-paragraph distillation of company research **if provided**, optional contact name + channel, and a length guard (`max_chars`). Instructs: greet (use contact name if given) → role + one specific genuine hook tying strengths to the company → light CTA → sign with the candidate name.
- `await llm.complete(prompt, system=...)` → stripped body. `llm is None` → raise `OutreachUnavailableError` (route → 503).
- The generator is **pure** (takes strings); `OutreachService` resolves inputs.
- **`load_style_guide(path) -> str`** helper: reads the file; returns a built-in default voice string on missing/unreadable (logged once). Isolated + unit-testable.

### 3. `OutreachService` (orchestration over injected ports)

- **`generate(application_id, *, contact_name=None, channel=None) -> str`** — resolve tracked application (404 if missing) → profile (name/summary/skills via `get_current_profile`/`get_for_language`) → `research.get(app.company)` (sync, cache-only, `None` if absent) → `load_style_guide(path)` → `OutreachMessageGenerator.generate(...)`. **Records nothing** (re-runnable draft).
- **`record(application_id, *, kind, message=None, contact_name=None, channel=None) -> OutreachEvent`** — validate application exists + `kind` valid → `repo.add(...)`.
- **`list_for(application_id) -> list[OutreachEvent]`** — per-application timeline.
- **`due_followups() -> list[OutreachNudge]`** — stateless sweep over `repo.latest_per_application()`:
  ```
  for latest in repo.latest_per_application():
      if latest.kind == "sent"
         and (now - latest.created_at) >= cadence_days
         and (app := tracking.get(latest.application_id)) is not None
         and app.status in {saved, applied}:
          → OutreachNudge(application_id, app.company, latest.contact_name,
                          sent_at=latest.created_at, days_since=…)
  ```
  Idempotent (pure function of current events + statuses); recording `followed_up`/`replied` or advancing the status clears the nudge. Returns `[]` when nothing is due.

Dependencies: `tracking_service`, `profile_service`, `research_service`, `OutreachMessageGenerator`, `OutreachRepository`, `style_guide_path`, `followup_cadence_days`, `max_chars`. Single-responsibility, unit-testable with fakes.

### 4. API, cron & wiring

`outreach/api/` (provider/dependencies/routes/`__init__`, all auth-gated):
- `POST /outreach/generate` `{application_id, contact_name?, channel?}` → `{message}`. 404 unknown app; 503 no LLM.
- `POST /outreach/record` `{application_id, kind, message?, contact_name?, channel?}` → `OutreachEvent`. 422 invalid kind.
- `GET /outreach/events?application_id=…` → the per-application timeline.
- `POST /outreach/nudge` → `list[OutreachNudge]` (external-cron trigger, same pattern as `/autohunt/run`).

Bootstrap `build_outreach(infra, tracked, tracking_service, profile_service, research_service)` wired in `main.create_app()` **after tracking, profile, and research** (all already expose `.service` on their builds); constructs `OutreachRepository` + `OutreachMessageGenerator(tracked("outreach_message"))` + `OutreachService`. `app.state.outreach = build.provider`; include the router.

**Settings** (config + `.env.example`): `outreach_style_guide_path` (default `docs/reference/message_To_apprach_recruiters.md`), `outreach_followup_cadence_days` (default 7), `outreach_max_chars` (default 500), `outreach_followup_schedule` (informational-only cadence string).

## Error handling & edge cases

- **Unknown application** → 404 on generate/record/list; the nudge sweep skips events whose application no longer exists.
- **No LLM** → `generate` → 503; record/list/nudge unaffected.
- **No profile** → generate still runs (thinner message; neutral close if no name) — soft, no hard failure.
- **No cached research** → research paragraph omitted; never force-generates research.
- **Style-guide file missing** → built-in default voice; logged once; never blocks.
- **Invalid `kind`** → 422.
- **Nudge sweep** stateless/idempotent; double cron fire → same list; `[]` when nothing due.
- **Out-of-order events** (`replied` with no prior `sent`) → permitted; sweep only nudges when the latest event is `sent`.

## Testing

- **Unit — `OutreachMessageGenerator`** (fake LLM): prompt includes style guide + name + role; includes the research paragraph when provided, omits when None; strips output; raises when `llm is None`.
- **Unit — `load_style_guide`**: reads a temp file; default on missing path.
- **Unit — `OutreachService`** (fakes): `generate` resolves inputs + records nothing; `record` persists the right event; `due_followups` — sent>cadence & status applied → nudged; younger → not; latest followed_up/replied → not; status interviewing → not; unknown app → skipped.
- **Repo (SQLite)**: `add`/`list_for`/`latest_for`/`latest_per_application` round-trip against the `019` ORM, ordered by `created_at`.
- **Integration (FastAPI, real SQLite, fake LLM/profile/research, auth overridden):** generate returns a message; record `sent` then `GET /events` shows it; `/nudge` surfaces the app after back-dating the sent event past cadence, and returns `[]` after a `replied` event.

## Out of scope (future, own specs)

First-class contacts entity (recruiters across roles, warm-intro graph); outbound send (email/LinkedIn integration); an inbound-reply inbox (auto-detecting replies); the frontend compose/timeline UI; multi-user.

## Implementation sequencing note

Single cohesive plan; natural order: (1) `outreach_events` table + domain/repo + migration `019`; (2) `load_style_guide` + `OutreachMessageGenerator` (pure, unit-tested); (3) `OutreachService` (generate/record/list/due_followups) + unit tests; (4) API + bootstrap wiring + integration tests. Each step independently testable.
