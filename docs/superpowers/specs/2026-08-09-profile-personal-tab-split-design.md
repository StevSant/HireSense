# Splitting the Profile → Personal details page

**Date:** 2026-08-09
**Status:** Approved, ready to implement

## Problem

`/dashboard/profile/personal` stacks five independent cards in one column:

| # | Card | Write operations |
|---|------|------------------|
| 1 | Profile setup checklist | none (read-only progress) |
| 2 | Personal details | Edit toggle → 7-field form + Save |
| 3 | Apply profile | 7 fields + repeatable screening Q&A + Save |
| 4 | Portfolio projects | Sync button, per-project matching toggles, paginated grid |
| 5 | LinkedIn network | file import |

Three of them own an independent write action, and the tallest card (4, a paginated
project grid) sits between the user and the import control at the bottom. Reaching
the last form means scrolling past two unrelated tasks. The cards are not one
workflow — they are four separate ones sharing a scroll container.

## Approach

Split the page into three sibling tabs under the existing Profile hub, and hoist the
setup checklist so it spans all of them.

Rejected alternatives:

- **Two-column / accordion in one page.** Keeps a single route, but a wide layout
  still leaves the portfolio grid dominating and does nothing for narrow viewports.
- **One tab per card (four tabs).** Pushes the hub nav to six entries and gives the
  network import — a single file input — a page of its own.

## Design

### Routes and navigation

`HUBS.profile.tabs` grows from three entries to five:

| Label | Path | Contents |
|-------|------|----------|
| CV | `/dashboard/profile/cv` | unchanged |
| Personal details | `/dashboard/profile/personal` | personal details view/edit only |
| Apply profile | `/dashboard/profile/apply` | **new** — `app-apply-profile-card` |
| Sources | `/dashboard/profile/sources` | **new** — `app-portfolio-card` + `app-network-card` |
| Cover letters | `/dashboard/profile/cover-letters` | unchanged |

Two new lazy `loadComponent` children in `app.routes.ts`, matching the existing
profile children. `/personal` keeps its URL, so existing links and the CV tab's
cross-references stay valid.

The three card components move unchanged — re-parented, not rewritten — so their
existing specs remain valid.

### The setup checklist becomes the hub header

`ProfileSetupCardComponent` moves out of the Personal tab into
`profile.component.html`, rendered above `<router-outlet>` behind an
`@if (profile())` guard (its `profile` input is `input.required`). It therefore
shows on every Profile tab.

Each step gains a `route` field, and incomplete steps render as `routerLink`s:

| Step | Links to |
|------|----------|
| Add an email address | `/dashboard/profile/personal` |
| Add your location | `/dashboard/profile/personal` |
| Add a professional link | `/dashboard/profile/personal` |
| Add application basics | `/dashboard/profile/apply` |

Guidance strings change with the move: `"Use the Edit control below…"` becomes
`"Open Personal details to add it"`, since "below" is no longer true once the
control lives on another tab. This turns the checklist from a passive progress bar
into the section's primary navigation — it names what is missing and takes the user
there in one click, from anywhere in the hub.

### Per-tab empty states

The tabs have different profile requirements:

- **Personal** — requires a profile; keeps the current "No profile yet → upload a
  CV" state.
- **Apply** — also requires one (`input.required<CandidateProfile>`); gets the same
  state.
- **Sources** — requires nothing. `PortfolioCardComponent` and
  `NetworkCardComponent` drive their own services, which is why the current
  template deliberately parks them outside the `@if (profile())` block. On their
  own tab that caveat simply becomes the tab's contract.

Personal and Apply would otherwise duplicate identical empty-state markup, so it is
extracted into `ProfileRequiredEmptyStateComponent` under `components/`. It owns the
`RouterLink` to the CV tab.

## Files

**New**

- `tabs/apply-tab/profile-apply-tab.component.{ts,html,scss,spec.ts}`
- `tabs/sources-tab/profile-sources-tab.component.{ts,html,scss,spec.ts}`
- `components/profile-required-empty-state/profile-required-empty-state.component.{ts,html,scss}`

**Modified**

- `core/nav/hubs.const.ts` — two new tab entries
- `app.routes.ts` — two new lazy children
- `pages/profile/profile.component.{ts,html}` — hoisted checklist
- `components/profile-setup-card/` — `route` per step, reworded guidance, `routerLink`s
- `tabs/personal-tab/` — drops the three moved cards; drops the unused
  `initialLoading` computed (already dead — no template reads it)

Both new tabs `@use '../profile-tab-shared' as *;`, which is where `.details-card`
and `.empty-state` are defined.

## Testing

- **New:** apply-tab spec (form when a profile exists, empty state when not);
  sources-tab spec (both cards render with no profile loaded).
- **Updated:** personal-tab spec drops apply/portfolio/network assertions;
  `profile.component.spec.ts` asserts the checklist renders and links;
  `profile-setup-card.component.spec.ts` asserts each incomplete step carries the
  correct `routerLink`; `hub-for-url.spec.ts` covers the two new paths.

The frontend coverage gate is CI-enforced, so specs for the new tabs are required,
not optional.

Before pushing, run `npx ng lint` and the prettier check — both are CI gates that
`npm test` and `npm run build` skip.
