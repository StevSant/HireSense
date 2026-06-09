# Navigation Hubs & Profile/Account Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the dashboard sidebar into 5 tabbed hubs, fold Account into the Profile page, and add a "Replace CV" action — frontend only, no route-path or backend changes.

**Architecture:** A shared `HUBS` constant is the single source of truth for hub→tabs membership. `DashboardComponent` derives the active hub from the current URL (`hubForUrl`) to both highlight the sidebar and render a single `HubTabsComponent` above the router outlet. All existing route paths stay unchanged (zero broken links); only `/dashboard/account` becomes a redirect to `/dashboard/profile`. Profile keeps its internal signal tabs and gains an Account tab plus a Replace-CV button.

**Tech Stack:** Angular 21 (standalone components, signals, `input.required`, `OnPush`), Vitest, SCSS with global CSS custom properties.

**Spec:** `docs/superpowers/specs/2026-06-09-navigation-hubs-and-profile-account-design.md`

**Working directory for all commands:** `frontend/`

---

### Task 1: `HUBS` constant + nav types

**Files:**
- Create: `frontend/src/app/core/nav/hubs.const.ts`
- Create: `frontend/src/app/core/nav/index.ts`

- [ ] **Step 1: Create the constant and types**

Create `frontend/src/app/core/nav/hubs.const.ts`:

```ts
export type HubId = 'discover' | 'pipeline' | 'insights' | 'profile' | 'admin';

export interface HubTab {
  readonly label: string;
  readonly path: string;
}

export interface Hub {
  readonly id: HubId;
  readonly label: string;
  readonly tabs: readonly HubTab[];
}

export const HUBS: readonly Hub[] = [
  {
    id: 'discover',
    label: 'Discover',
    tabs: [
      { label: 'Ingestion', path: '/dashboard/ingestion' },
      { label: 'Matching', path: '/dashboard/matching' },
      { label: 'Auto-Hunt', path: '/dashboard/autohunt' },
    ],
  },
  {
    id: 'pipeline',
    label: 'Pipeline',
    tabs: [
      { label: 'Applications', path: '/dashboard/applications' },
      { label: 'Interview', path: '/dashboard/interview' },
      { label: 'Tracking', path: '/dashboard/tracking' },
      { label: 'Outreach', path: '/dashboard/outreach' },
    ],
  },
  {
    id: 'insights',
    label: 'Insights',
    tabs: [{ label: 'Analytics', path: '/dashboard/analytics' }],
  },
  {
    id: 'profile',
    label: 'Profile',
    tabs: [{ label: 'Profile', path: '/dashboard/profile' }],
  },
  {
    id: 'admin',
    label: 'Admin',
    tabs: [
      { label: 'LLM Settings', path: '/dashboard/admin/llm-settings' },
      { label: 'LLM Usage', path: '/dashboard/admin/usage' },
    ],
  },
];
```

- [ ] **Step 2: Create the barrel re-export**

Create `frontend/src/app/core/nav/index.ts`:

```ts
export { HUBS } from './hubs.const';
export type { Hub, HubId, HubTab } from './hubs.const';
```

- [ ] **Step 3: Commit** (correctness is verified by Task 2, whose test imports this constant)

```bash
git add src/app/core/nav/hubs.const.ts src/app/core/nav/index.ts
git commit -m "feat(frontend): add HUBS navigation constant"
```

---

### Task 2: `hubForUrl` helper (TDD)

**Files:**
- Create: `frontend/src/app/core/nav/hub-for-url.ts`
- Test: `frontend/src/app/core/nav/hub-for-url.spec.ts`
- Modify: `frontend/src/app/core/nav/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/core/nav/hub-for-url.spec.ts`:

```ts
import { hubForUrl } from './hub-for-url';

describe('hubForUrl', () => {
  it('maps a hub tab path to its hub id', () => {
    expect(hubForUrl('/dashboard/matching')).toBe('discover');
    expect(hubForUrl('/dashboard/applications')).toBe('pipeline');
    expect(hubForUrl('/dashboard/analytics')).toBe('insights');
    expect(hubForUrl('/dashboard/profile')).toBe('profile');
    expect(hubForUrl('/dashboard/admin/usage')).toBe('admin');
  });

  it('ignores query string and fragment', () => {
    expect(hubForUrl('/dashboard/matching?job_id=1')).toBe('discover');
    expect(hubForUrl('/dashboard/ingestion#top')).toBe('discover');
  });

  it('returns null for drill-down and unknown routes', () => {
    expect(hubForUrl('/dashboard/applications/1')).toBeNull();
    expect(hubForUrl('/dashboard/job/1')).toBeNull();
    expect(hubForUrl('/dashboard/company/Acme')).toBeNull();
    expect(hubForUrl('/dashboard/optimization')).toBeNull();
    expect(hubForUrl('/')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --include "**/hub-for-url.spec.ts"`
Expected: FAIL — cannot resolve `./hub-for-url`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/app/core/nav/hub-for-url.ts`:

```ts
import { HUBS, HubId } from './hubs.const';

/**
 * Resolve which hub a dashboard URL belongs to, by exact base-path match.
 * Query string and fragment are ignored. Drill-down/detail routes (e.g.
 * `/dashboard/applications/1`) have no hub tab and return null.
 */
export function hubForUrl(url: string): HubId | null {
  const path = url.split(/[?#]/)[0];
  for (const hub of HUBS) {
    if (hub.tabs.some((tab) => tab.path === path)) {
      return hub.id;
    }
  }
  return null;
}
```

- [ ] **Step 4: Add to the barrel**

Edit `frontend/src/app/core/nav/index.ts` — append:

```ts
export { hubForUrl } from './hub-for-url';
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- --include "**/hub-for-url.spec.ts"`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/app/core/nav/hub-for-url.ts src/app/core/nav/hub-for-url.spec.ts src/app/core/nav/index.ts
git commit -m "feat(frontend): add hubForUrl resolver for active-hub detection"
```

---

### Task 3: `HubTabsComponent` (TDD)

**Files:**
- Create: `frontend/src/app/core/nav/hub-tabs.component.ts`
- Create: `frontend/src/app/core/nav/hub-tabs.component.html`
- Create: `frontend/src/app/core/nav/hub-tabs.component.scss`
- Test: `frontend/src/app/core/nav/hub-tabs.component.spec.ts`
- Modify: `frontend/src/app/core/nav/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/core/nav/hub-tabs.component.spec.ts`:

```ts
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { HubTabsComponent } from './hub-tabs.component';
import { HUBS } from './hubs.const';

@Component({
  standalone: true,
  imports: [HubTabsComponent],
  template: '<app-hub-tabs [hub]="hub" />',
})
class HostComponent {
  hub = HUBS.find((h) => h.id === 'pipeline')!;
}

describe('HubTabsComponent', () => {
  it('renders one link per hub tab with the right labels and hrefs', () => {
    TestBed.configureTestingModule({
      imports: [HostComponent],
      providers: [provideRouter([])],
    });
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();

    const links = Array.from(
      fixture.nativeElement.querySelectorAll('a.hub-tab'),
    ) as HTMLAnchorElement[];

    expect(links.map((a) => a.textContent?.trim())).toEqual([
      'Applications',
      'Interview',
      'Tracking',
      'Outreach',
    ]);
    expect(links[0].getAttribute('href')).toBe('/dashboard/applications');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --include "**/hub-tabs.component.spec.ts"`
Expected: FAIL — cannot resolve `./hub-tabs.component`.

- [ ] **Step 3: Create the component class**

Create `frontend/src/app/core/nav/hub-tabs.component.ts`:

```ts
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Hub } from './hubs.const';

@Component({
  selector: 'app-hub-tabs',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './hub-tabs.component.html',
  styleUrl: './hub-tabs.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HubTabsComponent {
  hub = input.required<Hub>();
}
```

- [ ] **Step 4: Create the template**

Create `frontend/src/app/core/nav/hub-tabs.component.html`:

```html
<nav class="hub-tabs" role="tablist">
  @for (tab of hub().tabs; track tab.path) {
    <a
      class="hub-tab"
      role="tab"
      [routerLink]="tab.path"
      routerLinkActive="active"
      [routerLinkActiveOptions]="{ exact: true }"
    >
      {{ tab.label }}
    </a>
  }
</nav>
```

- [ ] **Step 5: Create the styles**

Create `frontend/src/app/core/nav/hub-tabs.component.scss` (mirrors the Profile page's `.page-tabs`/`.page-tab` look using global CSS custom properties):

```scss
.hub-tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-default);
}

.hub-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.1rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  color: var(--text-muted);
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  transition:
    color var(--duration) var(--ease),
    border-color var(--duration) var(--ease);

  &:hover {
    color: var(--text-secondary);
  }

  &.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
    font-weight: 600;
  }
}
```

- [ ] **Step 6: Add to the barrel**

Edit `frontend/src/app/core/nav/index.ts` — append:

```ts
export { HubTabsComponent } from './hub-tabs.component';
```

- [ ] **Step 7: Run test to verify it passes**

Run: `npm test -- --include "**/hub-tabs.component.spec.ts"`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/app/core/nav/hub-tabs.component.ts src/app/core/nav/hub-tabs.component.html src/app/core/nav/hub-tabs.component.scss src/app/core/nav/hub-tabs.component.spec.ts src/app/core/nav/index.ts
git commit -m "feat(frontend): add HubTabsComponent for in-hub tab navigation"
```

---

### Task 4: Wire hubs into `DashboardComponent` (TDD)

**Files:**
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.ts`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.html`
- Test: `frontend/src/app/pages/dashboard/dashboard.component.spec.ts`

Note: `dashboard.component.scss` is **not** modified — the existing `.sidebar nav a.active` rule (lines 136–142) is reused; we just drive `.active` with a class binding instead of `routerLinkActive`.

- [ ] **Step 1: Update the failing test**

Replace the entire contents of `frontend/src/app/pages/dashboard/dashboard.component.spec.ts`:

```ts
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { DashboardComponent } from './dashboard.component';
import { AuthService } from '../../core/services/auth.service';

function makeAuth(over: Partial<Record<string, unknown>> = {}) {
  return {
    logout: () => {},
    ...over,
  };
}

describe('DashboardComponent', () => {
  function mount(auth: unknown = makeAuth()) {
    TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [provideRouter([]), { provide: AuthService, useValue: auth }],
    });
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the navigation shell with the sidebar closed by default', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    expect(cmp.sidebarOpen()).toBe(false);
    expect(fixture.nativeElement.querySelector('aside.sidebar')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.dashboard-layout.sidebar-open')).toBeNull();
  });

  it('renders exactly five hub links in the sidebar', () => {
    const fixture = mount();
    const links = fixture.nativeElement.querySelectorAll('aside.sidebar nav a');
    expect(links.length).toBe(5);
  });

  it('highlights the hub that matches the active hub signal', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    cmp.activeHub.set('pipeline');
    fixture.detectChanges();

    const active = fixture.nativeElement.querySelector('aside.sidebar nav a.active');
    expect(active).not.toBeNull();
    expect(active.textContent).toContain('Pipeline');
  });

  it('exposes the hub tab bar for routed hubs but not for profile', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    cmp.activeHub.set('discover');
    expect(cmp.hubTabs()?.id).toBe('discover');

    cmp.activeHub.set('profile');
    expect(cmp.hubTabs()).toBeNull();

    cmp.activeHub.set(null);
    expect(cmp.hubTabs()).toBeNull();
  });

  it('toggles and closes the sidebar via signal updates', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    cmp.toggleSidebar();
    expect(cmp.sidebarOpen()).toBe(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.dashboard-layout.sidebar-open')).not.toBeNull();

    cmp.closeSidebar();
    expect(cmp.sidebarOpen()).toBe(false);
  });

  it('delegates logout to the auth service', () => {
    const logout = vi.fn();
    const fixture = mount(makeAuth({ logout }));

    fixture.componentInstance.logout();

    expect(logout).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --include "**/dashboard.component.spec.ts"`
Expected: FAIL — `cmp.activeHub` / `cmp.hubTabs` undefined, and 5-link assertion fails (11+ links today).

- [ ] **Step 3: Update the component class**

Replace the entire contents of `frontend/src/app/pages/dashboard/dashboard.component.ts`:

```ts
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterOutlet, RouterLink, Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { AuthService } from '../../core/services/auth.service';
import { HUBS, HubTabsComponent, hubForUrl } from '../../core/nav';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterOutlet, RouterLink, HubTabsComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  private auth = inject(AuthService);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

  sidebarOpen = signal(false);
  activeHub = signal(hubForUrl(this.router.url));

  hubTabs = computed(() => {
    const id = this.activeHub();
    if (!id || id === 'profile') return null;
    return HUBS.find((hub) => hub.id === id) ?? null;
  });

  constructor() {
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((e) => {
        this.sidebarOpen.set(false);
        this.activeHub.set(hubForUrl(e.urlAfterRedirects));
      });
  }

  toggleSidebar(): void {
    this.sidebarOpen.update((v) => !v);
  }

  closeSidebar(): void {
    this.sidebarOpen.set(false);
  }

  logout(): void {
    this.auth.logout();
  }
}
```

- [ ] **Step 4: Update the sidebar nav and content outlet**

In `frontend/src/app/pages/dashboard/dashboard.component.html`, replace the entire `<nav> … </nav>` block (current lines 26–146) with these 5 hub links:

```html
    <nav>
      <a [routerLink]="['ingestion']" [class.active]="activeHub() === 'discover'">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
        </span>
        <span>Discover</span>
      </a>
      <a [routerLink]="['applications']" [class.active]="activeHub() === 'pipeline'">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
          </svg>
        </span>
        <span>Pipeline</span>
      </a>
      <a [routerLink]="['analytics']" [class.active]="activeHub() === 'insights'">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"/>
            <line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </span>
        <span>Insights</span>
      </a>
      <a [routerLink]="['profile']" [class.active]="activeHub() === 'profile'">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </span>
        <span>Profile</span>
      </a>
      <a [routerLink]="['admin/llm-settings']" [class.active]="activeHub() === 'admin'">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.09a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </span>
        <span>Admin</span>
      </a>
    </nav>
```

Then change the `<main class="content">` block (current lines 151–153) to render the hub tab bar above the outlet:

```html
  <main class="content">
    @if (hubTabs(); as hub) {
      <app-hub-tabs [hub]="hub" />
    }
    <router-outlet />
  </main>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test -- --include "**/dashboard.component.spec.ts"`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add src/app/pages/dashboard/dashboard.component.ts src/app/pages/dashboard/dashboard.component.html src/app/pages/dashboard/dashboard.component.spec.ts
git commit -m "feat(frontend): collapse sidebar into 5 hubs with shared tab bar"
```

---

### Task 5: Redirect `/dashboard/account` → `/dashboard/profile`

**Files:**
- Modify: `frontend/src/app/app.routes.ts:29`

- [ ] **Step 1: Replace the account route with a redirect**

In `frontend/src/app/app.routes.ts`, replace line 29:

```ts
      { path: 'account', loadComponent: () => import('./pages/account/account.component').then(m => m.AccountComponent) },
```

with:

```ts
      { path: 'account', redirectTo: 'profile', pathMatch: 'full' },
```

(All other routes stay exactly as-is. `AccountComponent` is still imported directly by the Profile page in Task 6, so the file is not deleted.)

- [ ] **Step 2: Verify the app still builds**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add src/app/app.routes.ts
git commit -m "refactor(frontend): redirect /account to /profile"
```

---

### Task 6: Add the Account tab to the Profile page (TDD)

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.ts`
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Test: `frontend/src/app/pages/profile/profile.component.spec.ts`

- [ ] **Step 1: Write the failing test**

In `frontend/src/app/pages/profile/profile.component.spec.ts`:

(a) Add an import at the top, after the existing service imports:

```ts
import { AuthService } from '../../core/services/auth.service';
```

(b) In the `mount(...)` helper's `providers` array, add an `AuthService` stub (so the embedded `<app-account />` can resolve it when the Account tab is shown):

```ts
        { provide: AuthService, useValue: { me: () => of({ username: 'ada-user', role: 'admin' }), logout: () => {} } },
```

(c) Add this test inside the `describe` block:

```ts
  it('shows the Account tab content when the account tab is active', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const cmp = fixture.componentInstance;

    cmp.pageTab.set('account');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('ada-user');
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --include "**/profile.component.spec.ts"`
Expected: FAIL — `'account'` is not assignable to `pageTab`, and no account content renders.

- [ ] **Step 3: Update the component class**

In `frontend/src/app/pages/profile/profile.component.ts`:

(a) Add the import after the existing component imports (line 9 area):

```ts
import { AccountComponent } from '../account/account.component';
```

(b) Add `AccountComponent` to the `imports` array of the `@Component` decorator.

(c) Widen the tab union type:

```ts
type ProfilePageTab = 'cv' | 'personal' | 'cover-letters' | 'account';
```

- [ ] **Step 4: Add the Account tab button and panel**

In `frontend/src/app/pages/profile/profile.component.html`:

(a) After the Cover letters tab `<button>` (the one ending `Cover letters</button>`, current line 34), add a 4th tab button:

```html
    <button
      type="button"
      role="tab"
      class="page-tab"
      [class.active]="pageTab() === 'account'"
      (click)="pageTab.set('account')"
    >
      Account
    </button>
```

(b) After the cover-letters `@if (pageTab() === 'cover-letters') { … }` section (ends at current line 429), add the account panel:

```html
  @if (pageTab() === 'account') {
  <section class="tab-panel">
    <app-account />
  </section>
  }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- --include "**/profile.component.spec.ts"`
Expected: PASS (all existing tests + the new one).

- [ ] **Step 6: Commit**

```bash
git add src/app/pages/profile/profile.component.ts src/app/pages/profile/profile.component.html src/app/pages/profile/profile.component.spec.ts
git commit -m "feat(frontend): fold Account into Profile as a tab"
```

---

### Task 7: Add the "Replace CV" action (TDD)

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.ts`
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Test: `frontend/src/app/pages/profile/profile.component.spec.ts`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/app/pages/profile/profile.component.spec.ts` inside the `describe` block:

```ts
  it('replaceCv pre-selects the active language and opens the upload form', () => {
    const { fixture, profileService } = mount({ profiles: { en: makeProfile() } });
    const cmp = fixture.componentInstance;
    (profileService.activeLanguage as { set: (v: string) => void }).set('en');

    cmp.replaceCv();

    expect(cmp.showUploadForm()).toBe(true);
    expect(cmp.uploadIntent()).toBe('replace');
    expect(cmp.language()).toBe('en');
    expect(cmp.selectedFile()).toBeNull();
  });

  it('addAnotherLanguage marks the intent as add', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const cmp = fixture.componentInstance;

    cmp.addAnotherLanguage();

    expect(cmp.showUploadForm()).toBe(true);
    expect(cmp.uploadIntent()).toBe('add');
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --include "**/profile.component.spec.ts"`
Expected: FAIL — `cmp.replaceCv` and `cmp.uploadIntent` are undefined.

- [ ] **Step 3: Update the component class**

In `frontend/src/app/pages/profile/profile.component.ts`:

(a) Add the signal near the other signals (after `showUploadForm`):

```ts
  uploadIntent = signal<'add' | 'replace'>('add');
```

(b) Set the intent in `addAnotherLanguage()` — add this as the first line of the method body:

```ts
    this.uploadIntent.set('add');
```

(c) Reset the intent in `cancelUpload()` — add to its body:

```ts
    this.uploadIntent.set('add');
```

(d) Add the new handler (place it next to `addAnotherLanguage`):

```ts
  replaceCv(): void {
    this.language.set(this.activeLanguage());
    this.uploadIntent.set('replace');
    this.selectedFile.set(null);
    this.error.set('');
    this.showUploadForm.set(true);
  }
```

- [ ] **Step 4: Update the template**

In `frontend/src/app/pages/profile/profile.component.html`:

(a) Replace the `+ Add Language` button (current line 205) with a two-button action group:

```html
        <div class="profile-header-actions">
          <button (click)="replaceCv()" class="btn-secondary">Replace CV</button>
          <button (click)="addAnotherLanguage()" class="btn-secondary">+ Add Language</button>
        </div>
```

(b) Make the inline upload-form heading intent-aware. Replace the current heading (line 227):

```html
            <h3>Upload {{ language() === 'es' ? 'Spanish' : 'English' }} CV</h3>
```

with:

```html
            <h3>{{ uploadIntent() === 'replace' ? 'Replace' : 'Upload' }} {{ language() === 'es' ? 'Spanish' : 'English' }} CV</h3>
```

- [ ] **Step 5: Add minimal layout style for the action group**

Append to `frontend/src/app/pages/profile/profile.component.scss`:

```scss
.profile-header-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npm test -- --include "**/profile.component.spec.ts"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/app/pages/profile/profile.component.ts src/app/pages/profile/profile.component.html src/app/pages/profile/profile.component.scss src/app/pages/profile/profile.component.spec.ts
git commit -m "feat(frontend): add Replace CV action to the profile view"
```

---

### Task 8: Full verification + lint

**Files:** none (verification only).

- [ ] **Step 1: Run the full frontend test suite**

Run: `npm test`
Expected: all specs pass.

- [ ] **Step 2: Lint (CI runs this; npm test/build skip it)**

Run: `npx ng lint`
Expected: no errors. Fix any reported issues inline, then re-run.

- [ ] **Step 3: Production build sanity check**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual smoke test (dev server)**

Run: `npm start`, then in the browser:
- Sidebar shows exactly 5 items: Discover, Pipeline, Insights, Profile, Admin.
- Clicking **Discover** lands on Ingestion and shows a tab bar (Ingestion / Matching / Auto-Hunt); switching tabs keeps Discover highlighted.
- **Pipeline** shows Applications / Interview / Tracking / Outreach.
- Opening an application detail (`/dashboard/applications/<id>`) shows **no** hub tab bar and no hub highlighted.
- **Profile** shows its own CV / Personal details / Cover letters / **Account** tabs (no hub tab bar).
- Profile → CV, with a profile present, shows **Replace CV** next to **+ Add Language**; clicking Replace CV opens the inline form titled "Replace … CV" pre-set to the current language.
- Navigating to `/dashboard/account` redirects to the Profile page.

- [ ] **Step 5: Final commit (only if lint/build forced any fixes)**

```bash
git add -A
git commit -m "chore(frontend): lint and build fixes for navigation hubs"
```

---

## Notes on the open question (from the spec)

**Insights single-tab bar:** Analytics is the only tab in Insights, so the hub tab bar shows one lone tab. This plan **renders it anyway** for visual consistency across hubs. If you'd rather hide the bar for single-tab hubs, change the `hubTabs` computed in `DashboardComponent` (Task 4, Step 3) to also return `null` when `hub.tabs.length < 2`. Left as-is by default.
