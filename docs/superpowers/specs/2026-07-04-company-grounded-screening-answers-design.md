# Company-grounded screening-question answers — design

**Date:** 2026-07-04
**Status:** Approved (design), pending implementation plan

## Problem

Job applications frequently ask free-text screening questions such as
"Why are you interested in working at X?" or "¿Tienes conocimientos y/o
experiencia utilizando Django y React? Si es así, cuéntanos en profundidad."
Answering these well requires knowing both the candidate (profile) and the
company (facts + culture). Today the user answers these by hand.

HireSense already has most of the pieces but they aren't connected:

- **`research` module** — LLM-generates company research (funding stage, tech
  stack, culture, growth, pros/cons) keyed by company name, cached in DB, with
  `/research` endpoints and a frontend `research.service.ts`. It relies purely
  on the model's own knowledge — it never fetches *real* company data.
- **`ScreeningAnswer`** — a manual answer bank on `ApplyProfile`
  (`{question, answer}` pairs). Nothing *generates* answers.
- **GetOnBoard adapter** already calls `/companies/{id}` during ingestion but
  discards everything except the company name.
- **Company page** (`/dashboard/company/<name>`) shows only the jobs table — no
  company info.

## Goal

1. Source **real** company info from job portals where an API exists, with LLM
   research as the universal fallback (hybrid).
2. Use that grounding + the candidate profile + the specific job description to
   **draft answers** to screening questions, on demand, in the question's
   language.
3. **Display** company info on the company detail page.

## Non-goals (YAGNI)

- No per-portal company adapters beyond GetOnBoard for now (most boards —
  LinkedIn, Remotive, Jobicy, RemoteOK, WeWorkRemotely — expose no company API).
- No auto-generation of answers to a fixed question set. Drafting is on demand.
- No standalone company-info API fetch endpoint; portal facts are captured
  opportunistically during ingestion (zero extra HTTP cost).

## Data flow

```
Portal company API (GetOnBoard /companies/{id})  ─┐
                                                  ├─► CompanyInfo cache (facts)  ─┐
LLM company research (existing, universal)  ──────┘   CompanyResearch (analysis) ─┤
                                                                                  ├─► Screening-answer drafter
Candidate profile + job snapshot (JD, required skills) ────────────────────────── ┘   (LLM, answers in the question's language)
```

Grounding precedence for a company: **portal facts (`CompanyInfo`) when
present, else LLM `CompanyResearch`**. Both feed the company page and the
answer drafter. This mirrors the existing `outreach` module, which already
combines `research_service` + `profile` + an LLM to draft outreach messages.

## Backend

### Company info (real-data layer) — in the `research` module

- **`CompanyInfo`** domain model (Pydantic): `id`, `company_name`,
  `description`, `website`, `industry`, `size`, `logo_url`, `source`
  (e.g. `"getonboard"`), `source_ref` (the portal company id/slug),
  `created_at`, `updated_at`. Optional fields default to `None`.
- **`CompanyInfoRepositoryPort`** (Protocol) + `CompanyInfoOrm` + repository,
  cached/looked-up by **normalized company name** (case-insensitive, trimmed).
  The ORM is registered in `infrastructure/registry.py` and gets an Alembic
  migration.
- **Opportunistic capture during ingestion:** the GetOnBoard adapter already
  fetches `/companies/{id}`. Extend it to keep the full company payload
  (`name`, `long_description`/`description`, `website`, `logo`, industry/size
  where present) and have the ingestion path upsert a `CompanyInfo` row. To
  keep the dependency one-directional (ingestion → research, never the
  reverse), ingestion writes through a small **`CompanyInfoSinkPort`** injected
  at bootstrap; the research repository provides the implementation.
- Companies with no portal facts (e.g. SeatGeek, sourced from LinkedIn) simply
  have no `CompanyInfo` row and fall back to LLM `CompanyResearch`.

### Answer drafter — in the `applications` module

- **`ScreeningAnswerService`** (mirrors `ApplyService`): depends on
  `tracking_service` (to load the application's job snapshot — JD + required
  skills + company/title), `profile_service` (candidate profile), a company
  grounding source (`CompanyInfo` if present, else `CompanyResearch`), and an
  LLM via `tracked("screening_answer")`.
- **Behavior:** given a question, build a prompt from
  profile + job snapshot + company grounding, and produce an answer **in the
  same language as the question** (the LLM detects and matches — so a Spanish
  question yields a Spanish answer). Degrades gracefully (clear error) if the
  application or profile is missing.
- **Endpoint:** `POST /applications/{id}/screening-answer` with body
  `{ "question": str }` → `{ "question": str, "answer": str, "language": str }`.
  Auth via the existing `require_auth` router dependency.
- **Save to bank:** reuses the existing `ScreeningAnswer` bank on the profile —
  a save action persists the `{question, answer}` pair through the existing
  profile apply-profile update path, so it's reusable next time.

### Bootstrap / wiring

- `build_research` also constructs the `CompanyInfo` repository and exposes it
  (and the `CompanyInfoSinkPort`) on the research provider.
- Ingestion bootstrap receives the `CompanyInfoSinkPort`.
- Applications bootstrap constructs `ScreeningAnswerService` with
  `tracked("screening_answer")`, `profile_service`, `tracking_service`, and the
  research provider's grounding lookup; exposed via the applications provider +
  `api/dependencies.py`.
- New config in `config.py` + `.env.example` if any threshold/limit is needed
  (e.g. max question length, answer token budget). No hardcoded values.

## Frontend

- **Application detail page** — a "Screening question" card: a textarea for the
  question, a **Draft answer** button (calls
  `POST /applications/{id}/screening-answer`), then renders the answer with
  **Copy** and **Save to answer bank** actions. Signals for state; OnPush.
- **Company page** (`/dashboard/company/<name>`) — a company card at the top
  showing the description + facts from `CompanyInfo` and/or the LLM research
  summary. Cached data loads automatically on a cheap GET; if nothing is
  cached, a **Research company** button generates it on demand (avoids burning
  LLM tokens on every page view).
- Services/models: extend `research.service.ts` (or add a small
  screening-answer service) and add a `CompanyInfo` model; a
  `company-info.model.ts` and screening-answer request/response models.

## Testing

- **Unit (backend):** `CompanyInfo` repository (upsert/lookup by normalized
  name); GetOnBoard company-payload extraction; `ScreeningAnswerService` with
  fake LLM/profile/tracking, including language matching and missing-data
  fallbacks.
- **Integration (backend):** `POST /applications/{id}/screening-answer` and the
  company-info GET against in-memory SQLite (existing conventions:
  `require_auth` override, `StaticPool` sqlite).
- **Frontend:** Vitest specs for the screening-question card (draft, copy, save)
  and the company card (cached load, on-demand research).

## Implementation order

1. Company info: model, port, ORM, repository, migration, GetOnBoard capture,
   ingestion sink wiring — this grounds everything else.
2. Answer drafter: service, endpoint, bootstrap wiring, save-to-bank.
3. Frontend: company card, then screening-question card.

## Risks / notes

- Portal facts only exist for GetOnBoard-sourced companies; LinkedIn/Remotive/etc.
  companies rely on LLM research. This is expected from the hybrid choice.
- Company page is keyed by company *name*; `CompanyInfo` lookup must normalize
  names consistently with how the company page derives the name from jobs.
- Migration must be applied to the dev DB after merge (CI runs on SQLite) —
  `uv run python -m alembic upgrade head`.
