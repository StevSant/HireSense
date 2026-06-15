# Apply Assist — Phase 2 browser-extension client (handoff spec)

**Date:** 2026-06-14
**Status:** v1 shipped as an in-monorepo **userscript** (not a separate-repo extension)
**Depends on:** Phases 0, 1, 2-backend (all shipped — see [[project-apply-assist]])

> **Implemented 2026-06-14 as a userscript**, per the user's preference to avoid a
> separate repo. Lives at `frontend/public/apply-assist.user.js` (served at
> `/apply-assist.user.js`); the tested matching core is `frontend/src/app/apply-assist/field-matcher.ts`.
> v1 calls `GET /profile/prefill` (no app-id needed) and uses an embedded label
> map mirroring the backend, rather than the `/applications/{id}/autofill-plan`
> endpoint. The MV3-extension design below remains the reference for a richer
> future client. Known v1 limits: text/select fields only (file inputs are
> manual), label-substring matching, token pasted once into the userscript
> manager, `API_BASE` edited at the top of the script.

## Why this is a separate deliverable

The extension is a Chrome/Edge **MV3** package (manifest + content script + popup)
that runs in the user's own authenticated browser session on third-party ATS
pages. It cannot live in, or be tested by, the HireSense backend+Angular monorepo
harness. Everything it depends on is already built and tested server-side; this
doc is the contract so it can be built standalone.

## Design principle (non-negotiable)

**Prefill + review + user clicks Submit.** Never headless auto-submit. This is the
only ToS-compliant, account-safe model (see the audit in [[project-apply-assist]]):
the extension fills fields the user reviews, then the *user* presses the site's
own Submit button. No CAPTCHA solving, no background submission.

## Backend contract (already shipped)

1. **Which jobs are applyable** — from `GET /ingestion/jobs` / `/ingestion/jobs/{id}`:
   - `application_method`: `ats_form` | `redirect` | `unknown`
   - `ats_type`: `greenhouse` | `lever` | `ashby` | `workable` | `smartrecruiters` | `recruitee` | null
   - `apply_url`: the direct form URL when `ats_form`
   Only `ats_form` jobs are autofillable.

2. **Candidate field values** — `GET /profile/prefill` → flat JSON of canonical keys:
   `full_name, first_name, last_name, preferred_name, email, phone, location,
   linkedin_url, github_url, portfolio_url, work_authorization,
   requires_visa_sponsorship (bool), desired_salary, years_of_experience (int),
   willing_to_relocate (bool), start_availability`. Only known keys are present.
   (404 if the user has no profile yet.)

3. **The autofill plan** — `build_autofill_plan(ats_type, prefill)` in
   `applications/domain/ats_field_map.py` returns `FieldFill[]`
   (`canonical_key`, `value`, `label_patterns[]`). `label_patterns` are lowercase
   substrings to match against each form field's visible label. **Expose this via a
   small endpoint** (e.g. `GET /applications/{id}/autofill-plan` or
   `POST /outreach`-style) so the extension fetches a ready plan instead of
   reimplementing the map in JS — recommended first backend follow-up.

## Extension responsibilities

1. **Detect the ATS** from the active tab URL host (reuse the Phase 0 suffixes:
   `greenhouse.io`, `lever.co`, `ashbyhq.com`, `workable.com`,
   `smartrecruiters.com`, `recruitee.com`). No match → stay idle.
2. **Authenticate to HireSense** (the user's session/token) and fetch the prefill +
   autofill plan.
3. **Match fields**: for each `FieldFill`, find the form input whose associated
   `<label>` text (or `aria-label`/placeholder) contains any `label_pattern`; set
   its value and dispatch `input`/`change` events so the ATS's framework registers it.
4. **Attach documents**: offer the HireSense-generated CV + cover-letter PDFs
   (`GET /applications/{id}/cv.pdf`, `/cover-letter.pdf`) for the file inputs —
   browsers forbid programmatic file-input population, so download + prompt the user
   to attach, or use the native file picker.
5. **Highlight + review**: visually mark filled fields; never touch the Submit button.
6. **Confirm**: after the user submits, offer a "Mark as applied" action calling the
   existing `POST /applications/{id}/mark-applied`.

## Out of scope / known limits

- File inputs can't be set programmatically (browser security) — user attaches.
- Custom screening questions: surface the matching `screening_answers` for the user
  to paste; don't auto-answer free-text compliance questions.
- LinkedIn/Indeed Easy Apply: **deep-link only, no automation** (ToS).

## Suggested first backend follow-up

Add `GET /applications/{id}/autofill-plan` that combines the job's
`ats_type`/`apply_url` (from the application's job snapshot) with
`build_autofill_plan(ats_type, await profile_service.get_prefill())` so the
extension makes one call. Pure composition of already-shipped pieces.
