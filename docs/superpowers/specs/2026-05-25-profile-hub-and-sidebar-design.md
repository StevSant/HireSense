# Profile Hub & Sidebar Polish — Design

**Date:** 2026-05-25
**Scope:** Phase 1 only (frontend, no backend changes). Phases 2 and 3 are noted as follow-ups but out of scope for this spec.

## Problem

Two related discoverability/quality issues in the dashboard shell:

1. **Profile page is invisible as the CV home.** The sidebar entry is just "Profile" with a generic `&equiv;` (horizontal-lines) icon. Users don't realize CV upload lives there. The user explicitly said "no option for uploading our cv is available" — even though the upload UI is right at `/profile`.
2. **Sidebar formatting is rough.** All four nav icons are HTML entities (`&searr;`, `&equiv;`, `&#9728;`, `&raquo;`) which render at inconsistent sizes/weights and look unrelated to each other. The rest of the app uses inline SVGs (1.5–2px stroke, lucide-style). The "Career Intelligence" subtitle reads as a metadata label, not a tagline.

Phase 1 ships a frontend-only fix that addresses both issues and lays a discoverable foundation for Phase 2 (backend-backed Personal details + Cover letter library) and Phase 3 (Cover letter templates).

## Non-goals (this phase)

- No backend changes. No new endpoints, no schema changes, no migrations.
- No editable personal-details form (CV-parsed fields stay read-only).
- No cross-application cover letter library data (the tab exists as a signpost only).
- No cover letter templates.
- No new routes. `/profile` keeps its URL; the page becomes tabbed internally.

## Design

### 1. Sidebar redesign (`dashboard.component.html` + `.scss`)

**Icon replacement.** Swap each HTML-entity icon for an inline SVG with `width="18" height="18"`, `stroke="currentColor"`, `stroke-width="1.75"`, `fill="none"`, `stroke-linecap="round"`, `stroke-linejoin="round"`. Matches the existing Profile-page SVG style.

| Nav item | Icon (lucide name) | Why |
|---|---|---|
| Ingestion | `download` (tray with arrow into it) | Pulling jobs in from external portals |
| Profile | `user` (head + shoulders circle) | Standard "your stuff" affordance |
| Applications | `briefcase` | Universal "applying to jobs" mental model |
| Interview | `message-square` | Conversational prep tab |

Inline SVG paths (not external library) — keeps zero-dependency, matches the rest of the codebase.

**Spacing tweaks** in `dashboard.component.scss`:
- Increase nav-item vertical padding from `0.625rem 1.25rem` → `0.7rem 1.1rem` (more click target, less horizontal cramp).
- Increase gap between icon and label from `0.75rem` → `0.85rem`.
- Set `.nav-icon` to `display: inline-flex; align-items: center; justify-content: center; width: 1.25rem; height: 1.25rem` so icons land on a consistent baseline regardless of SVG bounding box.
- The "Career Intelligence" subtitle currently sits below the logo as `text-transform: uppercase, letter-spacing: 0.08em`. Keep the uppercase, but bump letter-spacing to `0.12em` for a more deliberate tagline feel, and lighten color to `var(--text-on-dark-muted)` at `0.7` opacity. Do **not** add italic. Tighten the visual relationship by changing the logo's `padding` shorthand from `1.5rem 1.25rem` → `1.25rem 1.25rem 1.5rem` (top, sides, bottom — keeps generous spacing below the subtitle while pulling the logo tighter to the top) and the subtitle `margin-top` from `0.15rem` → `0.25rem`. Net effect: tagline reads as "subtitle of HireSense" not "section header".

### 2. Profile page → tabbed hub (`profile.component.html` + `.ts` + `.scss`)

The page becomes a tabbed shell with three top-level tabs. URL stays `/profile`; tab state is a signal in the component (no router child routes — keeps the change small and avoids touching `app.routes.ts`).

```
┌─ My Profile ─────────────────────────────────────────┐
│  [ CV ]  [ Personal details ]  [ Cover letters ]     │
│  ───                                                  │
│                                                       │
│  <tab content>                                        │
└───────────────────────────────────────────────────────┘
```

#### Tab 1: **CV** (default)
Contains the **entire existing Profile page body** unchanged — upload card, language tabs, info-grid, skills, sections. All today's behavior is preserved verbatim; just wrapped in a tab panel.

#### Tab 2: **Personal details**
Read-only summary card showing what was parsed from the CV:
- Name, Email, Phone, Location, primary language

Below the card, a muted notice:
> *Edit and manual fields (LinkedIn, GitHub, portfolio) — coming soon. For now, these fields come from your CV.*

If no profile is uploaded yet, the tab shows a small empty state pointing back to the CV tab: "Upload a CV to see your parsed details here."

#### Tab 3: **Cover letters**
Two stacked cards:

1. **"Generate per-job"** — explainer card:
   > Cover letters are generated for each specific job in the **Applications** tab. Each one is tailored to that job's requirements and your CV. Open any application and use the *Apply* tab.

   Includes a `routerLink="/applications"` button: "Go to Applications".

2. **"Library — coming soon"** — disabled card showing the planned shape: an empty list with a muted placeholder row "You haven't generated any cover letters yet" and a "Coming soon" badge in the corner. Renders the same whether the user has 0 or 50 generated letters today — Phase 1 doesn't query for them.

### 3. Tab UX details

- Tab bar uses the **existing `.tab-bar` / `.tab` styles** already defined in `profile.component.scss` for the upload card. We promote those styles to the page level and reuse them — no new component, no new CSS pattern.
- Active tab signal: `pageTab = signal<'cv' | 'personal' | 'cover-letters'>('cv')` on the component.
- The existing `activeTab` signal (upload vs. paste-latex inside the upload card) is renamed to `uploadMode` to avoid name collision and make intent clearer.
- Tabs do **not** persist across navigation (no localStorage, no query param) — Phase 1 keeps it simple.

## Files touched

**Modify:**
- `frontend/src/app/pages/dashboard/dashboard.component.html` — replace HTML-entity icons with inline SVGs
- `frontend/src/app/pages/dashboard/dashboard.component.scss` — spacing/alignment polish in `.sidebar nav a` and `.logo`
- `frontend/src/app/pages/profile/profile.component.html` — wrap current body in CV tab, add Personal details and Cover letters tabs, add page-level tab bar
- `frontend/src/app/pages/profile/profile.component.ts` — add `pageTab` signal; rename `activeTab` → `uploadMode`
- `frontend/src/app/pages/profile/profile.component.scss` — promote `.tab-bar`/`.tab` styles to page level; add empty-state and "coming soon" styles for the new tabs

**Create:** None.

**Delete:** None.

## Testing

This is a UI-only change with no logic branching beyond signal-driven tab switching. Verification approach:

1. Type-check passes (`ng build` or equivalent).
2. Manually load `/profile` in browser:
   - All three tabs visible, CV is default-active.
   - Switching tabs swaps content without reloading the page.
   - Existing upload flow (PDF, LaTeX, language toggle, post-upload profile view) works identically inside the CV tab.
   - Personal details tab renders parsed fields when a profile exists; renders empty-state pointing to CV tab when none exists.
   - Cover letters tab "Go to Applications" button navigates to `/applications`.
3. Sidebar: all four icons render as SVGs at consistent size; active nav item still highlights with the accent border; mobile drawer still opens/closes via hamburger.

No unit tests added — existing Profile component has no tests today and Phase 1 doesn't introduce new logic worth covering. Phase 2 (when the cover-letter library fetch lands) will warrant tests for the service call.

## Rollout

Single PR. No feature flag — change is purely cosmetic/structural with no user-data risk. If the user dislikes the tab split, revert is one commit.

## Phase 2 / Phase 3 — out of scope, noted for continuity

So future-me knows the staged plan:

**Phase 2 (backend + wiring):**
- `GET /applications/cover-letters` aggregator endpoint that returns all `application_cover_letters` rows joined with the parent `tracked_applications` (job title, company, applied state). Powers the Cover letters → Library tab.
- `PATCH /profile/{id}` accepting `{ linkedin_url?, github_url?, portfolio_url?, location_override? }`. Requires migration adding those columns to `candidate_profiles` and updating `CandidateProfile` domain model + frontend model.
- Personal details tab gains an Edit mode.

**Phase 3 (cover letter templates):**
- New `cover_letter_templates` table (id, name, body, tone, language, created_at).
- CRUD endpoints under `/profile/cover-letter-templates`.
- Generator (`cover_letter_generator.py`) gains optional `template_id` to seed the prompt.
- Profile → Cover letters tab gains a third card: "Templates" with create/edit/delete.
