# Navigation Hubs & Profile/Account Merge — Design

**Date:** 2026-06-09
**Scope:** Frontend only. No backend changes, no new endpoints, no migrations.

## Problem

Two related issues, both surfaced by the user:

1. **No obvious way to replace an existing CV.** The Profile → CV tab only shows the upload card when *no* profile exists (`@else if (!profile())`). Once a profile is parsed, the only re-upload entry point is the `+ Add Language` button, which is framed (and coded) for adding a *second language* — it pre-selects an un-uploaded language. There is no clear "replace the CV I already have" action.
2. **The sidebar is too long and mixes responsibilities.** Eleven-plus flat links (Ingestion, Profile, Applications, Interview, Matching, Tracking, Outreach, Auto-Hunt, Analytics, LLM Settings, LLM Usage, Account). "Profile" and "Account" are both facets of "you" but occupy two separate top-level slots; the rest is an undifferentiated wall of links.

## Goals

- Collapse the sidebar to **5 grouped hubs**, each a tabbed page.
- Fold **Account** into the Profile hub as a tab (drop its standalone sidebar slot).
- Add a clear **Replace CV** action to the Profile → CV view.

## Non-goals

- No backend changes, no new endpoints, no migrations.
- **No route path changes.** Every existing URL (`/dashboard/ingestion`, `/dashboard/matching`, …) keeps its exact path. This is the central risk-reduction decision (see Approach below).
- No redirect routes beyond the single `account → profile` case.
- No collapsible/accordion sidebar behavior — hubs are flat sidebar items; tabs live on the page.

## Approach decision: presentational tab bar, flat URLs (Approach A)

The chosen wiring keeps all current route paths unchanged. A new presentational `HubTabsComponent` renders the sibling tabs (as `routerLink`s to the existing flat paths) at the top of each grouped page. The sidebar collapses to 5 items; the active hub is derived from the current URL via a route→hub lookup.

**Why A over nested routes (`/dashboard/discover/matching`):** ~20 internal navigations use absolute paths (`router.navigate(['/dashboard/applications', id])`, `routerLink="/dashboard/ingestion"`, etc.). Prefixed URLs would force rewriting all of them **plus** adding redirect routes for old bookmarks — more churn, more places to miss. Approach A delivers the identical visual result (5 sidebar items + tabbed hubs) with zero broken links and no redirects. For a single-user app, the URL not encoding the group name is immaterial.

## Design

### 1. The 5 hubs

| Hub | Tabs (existing pages) | Default tab | Guard |
|---|---|---|---|
| **Discover** | Ingestion · Matching · Auto-Hunt | Ingestion | — |
| **Pipeline** | Applications · Interview · Tracking · Outreach | Applications | — |
| **Insights** | Analytics | Analytics | — |
| **Profile** | CV · Personal details · Cover letters · **Account** | CV | — |
| **Admin** | LLM Settings · LLM Usage | LLM Settings | `adminGuard` |

**Chromeless drill-down pages** (no sidebar entry, no hub tab bar — reached contextually, unchanged today): `applications/:id`, `job/:id`, `company/:name`, `optimization`.

### 2. Sidebar (`dashboard.component.html` + `.scss`)

Replace the current flat nav with 5 hub links. Each hub link:
- Targets the hub's **default tab path** (e.g. Discover → `routerLink="ingestion"`).
- Is highlighted as active whenever the current URL belongs to that hub — **not** via `routerLinkActive` (which would only match the default tab), but via a computed `activeHub()` signal driven by the router URL.

Active-hub derivation lives in `DashboardComponent`:

```ts
private static readonly HUB_BY_PATH: Record<string, string> = {
  ingestion: 'discover', matching: 'discover', autohunt: 'discover',
  applications: 'pipeline', interview: 'pipeline', tracking: 'pipeline', outreach: 'pipeline',
  analytics: 'insights',
  profile: 'profile', account: 'profile',
  'admin/llm-settings': 'admin', 'admin/usage': 'admin',
};
activeHub = signal<string>('discover'); // updated on NavigationEnd
```

`HUB_BY_PATH` is the single source of truth for hub membership; `HubTabsComponent` consumes the same mapping (shared constant) so sidebar and tab bar can't drift. The detail pages (`job`, `company`, `applications/:id`, `optimization`) intentionally have no entry → no hub highlighted, which is correct for a drill-down.

Reuse the existing inline-SVG icon style (`width="18" height="18"`, `stroke-width="1.75"`). Keep the existing `nav-section-label` styling where useful, but hub items are top-level (no section labels needed once the list is 5 long).

### 3. `HubTabsComponent` (new, shared)

A small standalone presentational component placed at the top of each grouped page.

- **Input:** `hub` (one of `'discover' | 'pipeline' | 'insights' | 'admin'`). Profile is excluded — it keeps its own internal signal-tab bar (see §4).
- **Renders:** a horizontal tab bar of `routerLink`s to each sibling page in the hub, with the current route's tab marked active via `routerLinkActive`.
- **Styling:** promote/reuse the existing `.page-tabs` / `.page-tab` styles already used by the Profile page so the tab bar looks identical everywhere. Extract those rules into a shared stylesheet or duplicate minimally — no new visual pattern.
- **Data:** a static `HUBS` constant maps each hub to its ordered list of `{ label, path }`. Single definition, imported by both the component and (for membership) the sidebar.

Placement: each grouped page template gets `<app-hub-tabs hub="discover" />` (etc.) as its first child, above the page's existing header/content. Five existing page templates get this one-line addition; no logic in those components changes.

Per the code-style rule (one symbol per file), the `HUBS` constant and the `HubTabsComponent` live in separate files, with the package `index.ts` re-exporting both.

### 4. Profile hub: Account tab + Replace CV

Profile already uses internal signal tabs (`pageTab = signal<'cv' | 'personal' | 'cover-letters'>('cv')`). Two changes:

**(a) Add Account as a 4th tab.** Extend the union to include `'account'`. Move the content of `AccountComponent` (username, role badge, single-user note, Sign Out) into a new `account` tab panel. Implementation: render the existing `AccountComponent` inside the tab panel (`<app-account />`) rather than re-implementing — it already encapsulates the `auth.me()` fetch and logout. Profile keeps signal tabs (not routed children) for consistency with its existing three tabs and because all four are facets of one logical page.

- Drop the `account` link from the sidebar.
- Add a redirect route `account → profile` in `app.routes.ts` so existing bookmarks/`logout`-adjacent links don't 404. (Optionally carry a `?tab=account` query param later; not required for v1.)

**(b) Replace CV button.** In the profile-view header (where `+ Add Language` lives, `profile.component.html:205`), add a **Replace CV** button next to it.

- New handler `replaceCv()` on the component: pre-selects the **currently active language** (`this.profileService.activeLanguage()`), clears any selected file/error, and sets `showUploadForm.set(true)` — reusing the exact inline upload form already rendered for `+ Add Language`.
- The inline form's heading is currently `Upload {{ language }} CV`. Make it reflect intent: when replacing the active language, it reads "Replace {{ language }} CV"; when adding, "Upload {{ language }} CV". Drive this with a small `uploadIntent = signal<'add' | 'replace'>('add')`.
- Upload path is unchanged — `uploadFile()` → `profileService.uploadFile(file, language)`. The backend already upserts a profile by language, so re-uploading the active language replaces it. No backend work.

`addAnotherLanguage()` stays as-is (pre-selects an un-uploaded language, `uploadIntent = 'add'`).

## Files touched

**Create:**
- `frontend/src/app/core/components/hub-tabs/hub-tabs.component.ts` — `HubTabsComponent`
- `frontend/src/app/core/components/hub-tabs/hub-tabs.component.html` / `.scss`
- `frontend/src/app/core/components/hub-tabs/hubs.const.ts` — `HUBS` definition (hub → ordered tabs)
- `frontend/src/app/core/components/hub-tabs/index.ts` — re-export both symbols
- `frontend/src/app/core/components/hub-tabs/hub-tabs.component.spec.ts`

**Modify:**
- `frontend/src/app/pages/dashboard/dashboard.component.html` — replace 11+ nav links with 5 hub links
- `frontend/src/app/pages/dashboard/dashboard.component.ts` — `activeHub` signal + `HUB_BY_PATH` derivation on `NavigationEnd`
- `frontend/src/app/pages/dashboard/dashboard.component.scss` — active-hub class hook (since `routerLinkActive` no longer drives it)
- `frontend/src/app/pages/dashboard/dashboard.component.spec.ts` — assert 5 hub links + active-hub logic
- `frontend/src/app/app.routes.ts` — add `account → profile` redirect (keep all other paths)
- `frontend/src/app/pages/profile/profile.component.ts` — add `'account'` to `pageTab` union; `uploadIntent` signal; `replaceCv()` handler
- `frontend/src/app/pages/profile/profile.component.html` — Account tab + `<app-account />`; Replace CV button; intent-aware inline-form heading
- `frontend/src/app/pages/profile/profile.component.spec.ts` — Account tab renders; Replace CV reveals form with current language
- Each grouped page template — add one `<app-hub-tabs hub="…" />` line as its first child (10 pages across the 4 routed hubs; Profile is excluded as it keeps its own internal tabs):
  Discover → `ingestion`, `matching`, `autohunt`; Pipeline → `applications`, `interview`, `tracking`, `outreach`; Insights → `analytics`; Admin → `admin-llm-settings`, `admin-usage`
  (Insights has a single tab; still render the bar for consistency, or skip — see Open question.)

**Delete:** None. `AccountComponent` is retained and reused inside the Profile tab.

## Testing

- **Unit (Vitest):**
  - `HubTabsComponent` renders the correct sibling tabs for each hub and marks the active one.
  - `DashboardComponent` exposes exactly 5 hub links; `activeHub()` resolves correctly for representative URLs (e.g. `/dashboard/matching` → `discover`, `/dashboard/account` → `profile`, `/dashboard/job/1` → none).
  - `ProfileComponent`: Account tab renders; `replaceCv()` sets `showUploadForm` true with the active language and `uploadIntent='replace'`.
- **Lint:** run `npx ng lint` before pushing — CI runs it; `npm test`/`npm run build` skip it (known gotcha).
- **Manual:** sidebar shows 5 items; clicking a hub lands on its default tab; switching tabs stays within the hub and keeps the hub highlighted; Replace CV on an existing profile reveals the upload form pre-set to the current language; `/dashboard/account` redirects to Profile.

## Rollout

Single frontend PR. No feature flag — structural/cosmetic, no user-data risk. Revertable in one commit.

## Open question (resolve during planning, low stakes)

- **Insights hub tab bar:** with only one tab (Analytics), rendering `<app-hub-tabs>` shows a lone tab. Acceptable for visual consistency, or skip the bar on single-tab hubs. Default: render it (consistency); trivially changed.
