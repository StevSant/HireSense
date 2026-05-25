# Profile Hub & Sidebar Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Phase 1 of the Profile Hub & Sidebar Polish design: replace HTML-entity sidebar icons with inline SVGs, polish sidebar spacing, and reframe the Profile page as a tabbed hub (CV / Personal details / Cover letters) so CV upload is discoverable and Phases 2–3 have a visible home.

**Architecture:** Frontend-only Angular change. No backend, no migrations, no new routes. The Profile page stays at `/dashboard/profile` but its body becomes a three-tab shell driven by a new `pageTab` signal. The existing upload-card's internal `activeTab` signal is renamed to `uploadMode` to avoid naming collisions. Two of the three tabs (Personal details, Cover letters) are intentionally signpost-only — they explain Phase 2/3 work without backing API calls.

**Tech Stack:** Angular 17+ standalone components, Angular signals, SCSS, FormsModule, RouterLink.

**Testing strategy:** No automated tests are added. This is pure UI restructuring with no logic branching beyond `signal === 'literal'` checks. The Profile component has no existing tests; introducing the Angular testing harness for cosmetic changes is YAGNI. Each task ends with explicit **manual verification** in a running dev server. Phase 2 (when real cross-application data lands) is where unit tests will earn their keep.

**Spec:** `docs/superpowers/specs/2026-05-25-profile-hub-and-sidebar-design.md`

---

## File Structure

**Modified files (5):**
- `frontend/src/app/pages/dashboard/dashboard.component.html` — swap HTML-entity icons for inline SVGs
- `frontend/src/app/pages/dashboard/dashboard.component.scss` — tighten nav padding, icon alignment, logo/subtitle spacing
- `frontend/src/app/pages/profile/profile.component.ts` — add `pageTab` signal, rename `activeTab` → `uploadMode`, add `RouterLink` to imports
- `frontend/src/app/pages/profile/profile.component.html` — wrap existing body in CV tab panel, add page tab bar + Personal details + Cover letters panels
- `frontend/src/app/pages/profile/profile.component.scss` — add `.page-tabs` variant, empty-state + "coming soon" card styles

**Created files:** None.
**Deleted files:** None.

---

## Task 1: Sidebar — replace HTML-entity icons with inline SVGs

**Files:**
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.html:22-36`

- [ ] **Step 1: Replace the four nav `<a>` blocks**

Open `frontend/src/app/pages/dashboard/dashboard.component.html` and replace lines 21-36 (the four `<a routerLink…>` blocks inside `<nav>`) with the SVG-icon versions below. Each SVG uses `width="18" height="18"`, `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `stroke-width="1.75"`, `stroke-linecap="round"`, `stroke-linejoin="round"` — matching the lucide-style SVGs already used inside `profile.component.html`.

Replace this block:

```html
      <a routerLink="ingestion" routerLinkActive="active">
        <span class="nav-icon">&searr;</span>
        <span>Ingestion</span>
      </a>
      <a routerLink="profile" routerLinkActive="active">
        <span class="nav-icon">&equiv;</span>
        <span>Profile</span>
      </a>
      <a routerLink="applications" routerLinkActive="active">
        <span class="nav-icon">&#9728;</span>
        <span>Applications</span>
      </a>
      <a routerLink="interview" routerLinkActive="active">
        <span class="nav-icon">&raquo;</span>
        <span>Interview</span>
      </a>
```

With this block:

```html
      <a routerLink="ingestion" routerLinkActive="active">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
        </span>
        <span>Ingestion</span>
      </a>
      <a routerLink="profile" routerLinkActive="active">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </span>
        <span>Profile</span>
      </a>
      <a routerLink="applications" routerLinkActive="active">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
          </svg>
        </span>
        <span>Applications</span>
      </a>
      <a routerLink="interview" routerLinkActive="active">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </span>
        <span>Interview</span>
      </a>
```

Icons chosen (lucide naming): `download` (Ingestion = pulling jobs in), `user` (Profile = your stuff), `briefcase` (Applications = applying to jobs), `message-square` (Interview = conversational prep).

- [ ] **Step 2: Manual verify in browser**

Start the dev server if not running:

```bash
cd frontend && npm start
```

Navigate to `http://localhost:4200/dashboard/ingestion`. Confirm:
- All four sidebar entries show a clean line-icon (no funky symbols).
- Icons are visually consistent in size and stroke weight.
- Hover and active states still highlight (the existing CSS targets `.nav-icon { opacity }`, which now applies to the inner `<svg>` — verify the active item's SVG looks crisper than inactive items).

If the active SVG doesn't visibly change opacity, that's expected behavior we'll address in Task 2's spacing/opacity polish — don't fix it here.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/dashboard/dashboard.component.html
git commit -m "feat(sidebar): replace HTML-entity icons with inline SVGs

Swaps &searr; &equiv; &#9728; &raquo; for lucide-style line icons
(download / user / briefcase / message-square) at consistent 18px,
1.75 stroke. Matches the SVG style already used inside Profile."
```

---

## Task 2: Sidebar — spacing & alignment polish

**Files:**
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.scss:72-92` (logo block)
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.scss:101-138` (nav `a` block)

- [ ] **Step 1: Tighten the logo block**

In `dashboard.component.scss`, replace the `.logo` block (currently lines 72-92) with:

```scss
  .logo {
    padding: 1.25rem 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border-sidebar);

    h2 {
      margin: 0;
      font-family: var(--font-display);
      font-size: 1.125rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      color: var(--text-on-dark);
    }

    .logo-sub {
      font-size: 0.6875rem;
      color: var(--text-on-dark-muted);
      opacity: 0.7;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-top: 0.25rem;
    }
  }
```

Changes:
- `padding`: `1.5rem 1.25rem` → `1.25rem 1.25rem 1.5rem` (tighter top, same sides, slightly more bottom)
- `.logo-sub`: `letter-spacing: 0.08em → 0.12em`, added `opacity: 0.7`, `margin-top: 0.15rem → 0.25rem`

- [ ] **Step 2: Refine the nav `a` block**

In the same file, replace the `nav { a { … } }` block (currently lines 101-138) with:

```scss
    a {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      padding: 0.7rem 1.1rem;
      color: var(--text-on-dark-muted);
      text-decoration: none;
      font-family: var(--font-body);
      font-size: 0.875rem;
      font-weight: 500;
      transition: all 0.15s var(--ease);
      border-left: 2px solid transparent;
      margin: 0 0.5rem;
      border-radius: 0 var(--radius-md) var(--radius-md) 0;

      .nav-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.25rem;
        height: 1.25rem;
        opacity: 0.6;
        transition: opacity 0.15s var(--ease);

        svg { display: block; }
      }

      &:hover {
        color: var(--text-on-dark);
        background: var(--bg-sidebar-hover);

        .nav-icon { opacity: 0.9; }
      }

      &.active {
        color: var(--text-on-dark);
        background: var(--bg-sidebar-active);
        border-left-color: var(--accent);

        .nav-icon { opacity: 1; }
      }
    }
```

Changes:
- `gap`: `0.75rem → 0.85rem`
- `padding`: `0.625rem 1.25rem → 0.7rem 1.1rem` (slightly taller, slightly tighter sides)
- `.nav-icon`: removed `font-size: 1rem` (no longer relevant for SVGs); added `display: inline-flex`, `align-items/justify-content: center`, fixed `width/height: 1.25rem` so every SVG lands on a consistent column regardless of its intrinsic bounding box. Removed `text-align: center` (replaced by flex centering).
- Added `svg { display: block; }` inside `.nav-icon` to drop the inline-element baseline gap that would otherwise misalign the icon vertically.

- [ ] **Step 3: Manual verify in browser**

Refresh `http://localhost:4200/dashboard/ingestion`. Confirm:
- Icons sit on a perfectly straight vertical column (the `n` in "Ingestion", "Interview" should align identically left).
- Active item's icon visibly brighter than inactive items.
- "Career Intelligence" subtitle reads as a tagline — slightly muted, more letter-spaced, with a touch more breathing room from the logo above it.
- No layout shift; sidebar width unchanged.
- Mobile: shrink the window below 768px and confirm hamburger still toggles the sidebar (no regression).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/dashboard/dashboard.component.scss
git commit -m "feat(sidebar): tighten spacing and align icon column

- Nav items: bump gap to 0.85rem, padding 0.7rem/1.1rem
- .nav-icon becomes a 1.25rem flex box so SVGs land on a
  consistent column regardless of intrinsic viewBox
- Logo subtitle: lighter opacity, wider letter-spacing for a
  tagline feel, slightly more breathing room from the logo"
```

---

## Task 3: Profile component — `pageTab` signal + rename `activeTab` → `uploadMode`

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.ts` (imports + signals)
- Modify: `frontend/src/app/pages/profile/profile.component.html` (rename references — Task 3 only, the tab shell comes in Task 4)

- [ ] **Step 1: Update `profile.component.ts`**

Open `frontend/src/app/pages/profile/profile.component.ts` and replace lines 1-16 with:

```typescript
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ProfileService } from '../../core/services/profile.service';
import { CandidateProfile } from './models/candidate-profile.model';

type ProfilePageTab = 'cv' | 'personal' | 'cover-letters';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  private profileService = inject(ProfileService);

  pageTab = signal<ProfilePageTab>('cv');
  uploadMode = signal<'upload' | 'paste'>('upload');
```

Changes:
- Add `RouterLink` import (Cover letters tab needs it in Task 6).
- Add the `ProfilePageTab` type alias.
- Add `RouterLink` to `imports: [...]`.
- Add `pageTab` signal above the renamed `uploadMode`.
- Rename `activeTab` → `uploadMode` (the rest of the file's signals stay verbatim).

- [ ] **Step 2: Rename `activeTab` references in `profile.component.html`**

In `frontend/src/app/pages/profile/profile.component.html`, replace every `activeTab` with `uploadMode`. There are three occurrences in the current file (lines 17, 18, 29, 30, 49 — five tokens across three logical references). Use a single edit:

Replace:
```html
          [class.active]="activeTab() === 'upload'"
          (click)="activeTab.set('upload')"
```
With:
```html
          [class.active]="uploadMode() === 'upload'"
          (click)="uploadMode.set('upload')"
```

Replace:
```html
          [class.active]="activeTab() === 'paste'"
          (click)="activeTab.set('paste')"
```
With:
```html
          [class.active]="uploadMode() === 'paste'"
          (click)="uploadMode.set('paste')"
```

Replace:
```html
        @if (activeTab() === 'upload') {
```
With:
```html
        @if (uploadMode() === 'upload') {
```

- [ ] **Step 3: Verify build + upload still works**

Run a type-check / build:

```bash
cd frontend && npm run build
```

Expected: build succeeds with no TypeScript errors (a build failure here means a rename was missed — grep for stragglers: `grep -n activeTab frontend/src/app/pages/profile/`).

Then in the browser, navigate to `/dashboard/profile`. If no profile exists, switch between "Upload File" and "Paste LaTeX" sub-tabs inside the upload card — both still work, no console errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/profile/profile.component.ts frontend/src/app/pages/profile/profile.component.html
git commit -m "refactor(profile): rename activeTab to uploadMode, add pageTab signal

Prepares for the page-level tab shell (CV / Personal / Cover letters).
The old activeTab signal was only ever tracking upload-vs-paste inside
the upload card; renaming clarifies intent and frees activeTab for the
new pageTab signal."
```

---

## Task 4: Profile template — wrap existing body in CV tab + add page tab bar

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Modify: `frontend/src/app/pages/profile/profile.component.scss` (add `.page-tabs` variant)

- [ ] **Step 1: Add `.page-tabs` variant to SCSS**

Append the following block to `frontend/src/app/pages/profile/profile.component.scss` (end of file):

```scss
// --- Page-level tab bar (CV / Personal / Cover letters) ---
.page-tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid $border;
}

.page-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.1rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  color: $text-light;
  font-size: 0.9rem;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: color $transition, border-color $transition;

  &:hover {
    color: $text-mid;
  }

  &.active {
    color: $primary;
    border-bottom-color: $primary;
    font-weight: 600;
  }
}

.tab-panel {
  // Tabs panels animate in subtly so users notice the switch.
  animation: tab-fade 0.18s ease;
}

@keyframes tab-fade {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}
```

Note: this is a *different* class (`.page-tabs` / `.page-tab`) from the existing `.tab-bar` / `.tab` used inside the upload card. Keeping them separate avoids visual collision and lets the page-level tabs feel slightly more prominent (larger font, no background tint).

- [ ] **Step 2: Update subtitle + add page tab bar in HTML**

In `frontend/src/app/pages/profile/profile.component.html`, replace lines 1-6 (the `.page-header` block) with:

```html
<div class="page">
  <div class="page-header">
    <h1>My Profile</h1>
    <p class="page-subtitle">Your CV, personal details, and cover letters in one place.</p>
  </div>

  <div class="page-tabs" role="tablist">
    <button
      type="button"
      role="tab"
      class="page-tab"
      [class.active]="pageTab() === 'cv'"
      (click)="pageTab.set('cv')"
    >
      CV
    </button>
    <button
      type="button"
      role="tab"
      class="page-tab"
      [class.active]="pageTab() === 'personal'"
      (click)="pageTab.set('personal')"
    >
      Personal details
    </button>
    <button
      type="button"
      role="tab"
      class="page-tab"
      [class.active]="pageTab() === 'cover-letters'"
      (click)="pageTab.set('cover-letters')"
    >
      Cover letters
    </button>
  </div>
```

- [ ] **Step 3: Wrap the existing body in a CV tab panel**

Still in `profile.component.html`, find the line `@if (initialLoading()) {` (was line 7, will have shifted after Step 2 — search for the literal string). Immediately **before** that `@if`, insert:

```html
  @if (pageTab() === 'cv') {
  <section class="tab-panel">
```

Then find the closing `</div>` at the end of the file (the one that closes `<div class="page">`, line 275 in the original). Immediately **before** that final `</div>`, insert:

```html
  </section>
  }
```

The result: the entire existing upload-card / profile-view tree is now wrapped inside `@if (pageTab() === 'cv') { <section class="tab-panel">…</section> }`. No internal changes to that content.

- [ ] **Step 4: Manual verify in browser**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

In the browser at `/dashboard/profile`:
- Three tabs visible: **CV** (active), **Personal details**, **Cover letters**.
- Clicking **Personal details** or **Cover letters** hides the CV content (those tabs show nothing yet — that's expected, they get content in Tasks 5 and 6).
- Clicking back to **CV** restores the full original UI (upload card if no profile, or profile-view if one exists). All sub-functionality (file upload, language toggle, etc.) still works.
- The subtle fade animation triggers on each tab switch.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/profile/profile.component.html frontend/src/app/pages/profile/profile.component.scss
git commit -m "feat(profile): wrap existing CV view in a tabbed page shell

The Profile page now has three top-level tabs (CV / Personal details /
Cover letters). The CV tab contains the entire existing experience
unchanged; the other two are stubs ready to be filled in next tasks."
```

---

## Task 5: Profile template — Personal details tab

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Modify: `frontend/src/app/pages/profile/profile.component.scss` (empty-state + details-card styles)

- [ ] **Step 1: Add Personal details panel to HTML**

In `frontend/src/app/pages/profile/profile.component.html`, immediately **after** the closing `}` of the CV tab block (i.e., after the `</section>\n  }` you added in Task 4 Step 3, and **before** the final `</div>` that closes `.page`), insert:

```html
  @if (pageTab() === 'personal') {
  <section class="tab-panel">
    @if (profile(); as p) {
      <div class="details-card">
        <div class="details-grid">
          <div class="details-item">
            <span class="details-label">Name</span>
            <span class="details-value">{{ p.name || '—' }}</span>
          </div>
          <div class="details-item">
            <span class="details-label">Email</span>
            <span class="details-value">{{ p.email || '—' }}</span>
          </div>
          <div class="details-item">
            <span class="details-label">Phone</span>
            <span class="details-value">{{ p.phone || '—' }}</span>
          </div>
          <div class="details-item">
            <span class="details-label">Location</span>
            <span class="details-value">{{ p.location || '—' }}</span>
          </div>
          <div class="details-item">
            <span class="details-label">Primary language</span>
            <span class="details-value">{{ p.language === 'es' ? 'Espanol' : 'English' }}</span>
          </div>
        </div>
        <p class="details-source-note">
          These fields were parsed from your uploaded CV.
        </p>
      </div>

      <div class="coming-soon-card">
        <div class="coming-soon-badge">Coming soon</div>
        <h3>Manual fields</h3>
        <p>Edit your name and location directly, and add LinkedIn, GitHub, and portfolio links that aren't on your CV.</p>
      </div>
    } @else {
      <div class="empty-state">
        <p class="empty-state-title">No profile yet</p>
        <p class="empty-state-hint">
          Upload a CV in the <button type="button" class="link-button" (click)="pageTab.set('cv')">CV tab</button> to see your parsed details here.
        </p>
      </div>
    }
  </section>
  }
```

- [ ] **Step 2: Add Personal-details + shared empty-state styles**

Append to `frontend/src/app/pages/profile/profile.component.scss` (end of file):

```scss
// --- Personal details tab ---
.details-card {
  background: $surface;
  border-radius: $radius;
  box-shadow: $shadow-sm;
  padding: 1.75rem;
  margin-bottom: 1.25rem;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.25rem 2rem;
  margin-bottom: 1.25rem;
}

.details-item {
  min-width: 0;
}

.details-label {
  display: block;
  font-size: 0.6875rem;
  color: $text-light;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}

.details-value {
  display: block;
  font-size: 0.95rem;
  color: $text-dark;
  font-weight: 500;
  word-break: break-word;
}

.details-source-note {
  margin: 0;
  padding-top: 1rem;
  border-top: 1px solid $border;
  font-size: 0.8rem;
  color: $text-light;
  font-style: italic;
}

// --- "Coming soon" card (shared with Cover letters tab) ---
.coming-soon-card {
  position: relative;
  background: $surface;
  border: 1px dashed $border;
  border-radius: $radius;
  padding: 1.5rem 1.75rem;
  color: $text-mid;

  h3 {
    margin: 0 0 0.4rem;
    font-size: 1rem;
    color: $text-dark;
    font-weight: 600;
  }

  p {
    margin: 0;
    font-size: 0.875rem;
    line-height: 1.55;
    color: $text-light;
  }
}

.coming-soon-badge {
  position: absolute;
  top: 1rem;
  right: 1rem;
  padding: 0.2rem 0.55rem;
  background: $primary-light;
  color: $primary-dark;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

// --- Empty state (shared across tabs) ---
.empty-state {
  background: $surface;
  border-radius: $radius;
  box-shadow: $shadow-sm;
  padding: 3rem 2rem;
  text-align: center;
}

.empty-state-title {
  margin: 0 0 0.4rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: $text-dark;
}

.empty-state-hint {
  margin: 0;
  font-size: 0.9rem;
  color: $text-light;
}

// --- Inline link-styled button (e.g. "CV tab" link inside empty state) ---
.link-button {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: $primary;
  font-weight: 500;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;

  &:hover {
    color: $primary-dark;
  }
}
```

- [ ] **Step 3: Manual verify**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

Browser flow:
1. With a profile uploaded — click **Personal details** tab → see the details card with name/email/phone/location/language, plus the "Coming soon — manual fields" card below it. Values fall back to `—` for missing fields.
2. With no profile (or sign out and create a fresh account) — click **Personal details** tab → see the empty state with a working inline "CV tab" link button that switches to the CV tab.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/profile/profile.component.html frontend/src/app/pages/profile/profile.component.scss
git commit -m "feat(profile): Personal details tab with read-only CV-parsed fields

Shows name/email/phone/location/language parsed from the CV, plus a
'Coming soon' card signposting Phase 2's editable manual fields
(LinkedIn, GitHub, portfolio). Empty state for users with no CV yet
links back to the CV tab."
```

---

## Task 6: Profile template — Cover letters tab

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Modify: `frontend/src/app/pages/profile/profile.component.scss` (per-job-card style)

- [ ] **Step 1: Add Cover letters panel to HTML**

In `frontend/src/app/pages/profile/profile.component.html`, immediately **after** the closing `}` of the Personal details block from Task 5 Step 1, and **before** the final `</div>` that closes `.page`, insert:

```html
  @if (pageTab() === 'cover-letters') {
  <section class="tab-panel">
    <div class="per-job-card">
      <div class="per-job-icon" aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
          <polyline points="22,6 12,13 2,6"/>
        </svg>
      </div>
      <div class="per-job-body">
        <h3>Generated per job</h3>
        <p>
          Cover letters are tailored to each specific job in the <strong>Applications</strong> tab.
          Open any application and use the <em>Apply</em> tab to generate one matched to the job
          and your CV.
        </p>
        <a routerLink="/dashboard/applications" class="btn-primary per-job-cta">
          Go to Applications
        </a>
      </div>
    </div>

    <div class="coming-soon-card">
      <div class="coming-soon-badge">Coming soon</div>
      <h3>Library</h3>
      <p>A single view of every cover letter you've generated, across all applications. Search, copy, and reuse without digging through each job.</p>
    </div>

    <div class="coming-soon-card">
      <div class="coming-soon-badge">Coming soon</div>
      <h3>Templates</h3>
      <p>Reusable cover letter templates you can pick from when applying — set the tone, opening, and signature once.</p>
    </div>
  </section>
  }
```

- [ ] **Step 2: Add per-job-card styles**

Append to `frontend/src/app/pages/profile/profile.component.scss` (end of file):

```scss
// --- Cover letters: per-job explainer card ---
.per-job-card {
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
  background: $surface;
  border-radius: $radius;
  box-shadow: $shadow-sm;
  padding: 1.5rem 1.75rem;
  margin-bottom: 1.25rem;
}

.per-job-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: $primary-light;
  color: $primary;
  border-radius: 10px;
  flex-shrink: 0;
}

.per-job-body {
  flex: 1;
  min-width: 0;

  h3 {
    margin: 0 0 0.4rem;
    font-size: 1rem;
    color: $text-dark;
    font-weight: 600;
  }

  p {
    margin: 0 0 1rem;
    font-size: 0.9rem;
    line-height: 1.6;
    color: $text-mid;
  }
}

.per-job-cta {
  text-decoration: none;
  display: inline-flex;
}
```

- [ ] **Step 3: Manual verify**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

Browser:
1. Click **Cover letters** tab → see three stacked cards: "Generated per job" with a "Go to Applications" button, then "Library — Coming soon", then "Templates — Coming soon".
2. Click "Go to Applications" → routes to `/dashboard/applications` (sidebar's Applications item should highlight).
3. Use the browser back button to return to Profile → Cover letters tab is no longer active (state doesn't persist across navigation, which is intentional Phase 1 behavior — tab resets to CV).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/profile/profile.component.html frontend/src/app/pages/profile/profile.component.scss
git commit -m "feat(profile): Cover letters tab signposting Apps flow + future work

Three cards: explainer + link to Applications (where per-job cover
letters are generated today), plus 'Coming soon' stubs for Library
and Templates (Phase 2 and Phase 3)."
```

---

## Task 7: Final verification

**Files:** None modified — this task is pure verification.

- [ ] **Step 1: Production build**

```bash
cd frontend && npm run build
```

Expected: build completes with no errors and no new warnings. If new warnings appear, investigate before proceeding.

- [ ] **Step 2: End-to-end smoke test in browser**

Start the dev server (`npm start` from `frontend/`) and walk the full surface:

**Sidebar:**
- Navigate to each of the four sections (Ingestion, Profile, Applications, Interview) — icons render as line SVGs, active highlight works on every page.
- Shrink browser to mobile width — hamburger toggles sidebar, all icons still render correctly.

**Profile — CV tab (default):**
- Logged-out → log in → land on Ingestion → click Profile → CV tab is active.
- If no profile exists: upload card visible with file/paste sub-tabs (the renamed `uploadMode` signal). Upload a small PDF or paste LaTeX. After successful upload, the profile view appears.
- Switch CV language tabs (if multiple languages uploaded) — still works.

**Profile — Personal details tab:**
- Click tab → details card shows parsed fields (or empty state if no CV).
- Inline "CV tab" link in empty state works.
- "Coming soon" badge visible top-right of the manual-fields card.

**Profile — Cover letters tab:**
- Click tab → three cards visible.
- "Go to Applications" navigates correctly.
- Both Coming Soon cards render with badges.

**Cross-tab navigation:**
- Switch between tabs rapidly — fade animation triggers, no flicker, no console errors.

- [ ] **Step 3: Final commit (only if any fixes were made during verification)**

If verification surfaced any issues that required fixes, commit them separately with a clear message describing what was fixed. If no fixes were needed, skip this step — there's nothing to commit.

---

## Self-review notes

**Spec coverage check:**
- Sidebar icon swap → Task 1 ✓
- Sidebar spacing polish (nav padding, icon column, logo subtitle) → Task 2 ✓
- Profile → tabbed shell, `pageTab` signal, `activeTab` → `uploadMode` rename → Tasks 3 + 4 ✓
- CV tab preserves existing behavior verbatim → Task 4 Step 3 (wrapping, no internal changes) ✓
- Personal details tab (read-only parsed fields + empty state + "coming soon" stub) → Task 5 ✓
- Cover letters tab (per-job explainer with Apps link + Library stub + Templates stub) → Task 6 ✓
- No new routes, no backend changes → confirmed (only frontend files modified) ✓
- Manual verification approach (no new unit tests) → each task has explicit browser verification steps ✓

**Type/naming consistency:**
- `pageTab` / `ProfilePageTab` type alias used consistently in TS (Task 3) and template (Tasks 4–6) ✓
- `uploadMode` rename applied to all five HTML references in Task 3 Step 2 ✓
- Tab values `'cv'` / `'personal'` / `'cover-letters'` match exactly across TS type and three template `@if` blocks ✓
- Route path `/dashboard/applications` matches `app.routes.ts:15` ✓
- `RouterLink` added to component imports in Task 3, first used in Task 6 ✓
- SCSS class names referenced in templates (`page-tabs`, `page-tab`, `tab-panel`, `details-card`, `details-grid`, `details-item`, `details-label`, `details-value`, `details-source-note`, `coming-soon-card`, `coming-soon-badge`, `empty-state`, `empty-state-title`, `empty-state-hint`, `link-button`, `per-job-card`, `per-job-icon`, `per-job-body`, `per-job-cta`) all defined in Tasks 4, 5, 6 ✓
