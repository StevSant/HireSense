# HireSense Frontend-Only Demo Implementation Plan

> **For Codex:** Execute this plan with test-first implementation and verify each milestone before deployment.

**Goal:** Ship a safe frontend-only HireSense demo on Vercel using synthetic, read-only data.

**Architecture:** A demo-specific Angular environment registers an HTTP interceptor before the existing API interceptors. The interceptor routes the app's current `/api` calls to typed, deterministic fixtures, while the normal builds retain the real network path. A small dashboard status rail makes the mode unambiguous.

**Tech Stack:** Angular 22, TypeScript, RxJS, Karma/Jasmine, SCSS, Vercel static hosting.

---

### Task 1: Demo API contract

**Files:**
- Create: `frontend/src/app/demo/demo-api.interceptor.spec.ts`
- Create: `frontend/src/app/demo/demo-api.interceptor.ts`
- Create: `frontend/src/app/demo/demo-fixtures.ts`

1. Write failing interceptor tests for demo authentication, paginated jobs, job detail, applications, analytics, prepared POST results, and blocked writes.
2. Run the focused tests and confirm they fail because the demo interceptor is absent.
3. Add the smallest fixture router that satisfies each test.
4. Re-run the focused tests after each behavior and refactor route matching into small helpers.

### Task 2: Isolated demo build

**Files:**
- Modify: `frontend/src/environments/environment.ts`
- Modify: `frontend/src/environments/environment.prod.ts`
- Create: `frontend/src/environments/environment.demo.ts`
- Modify: `frontend/src/app/app.config.ts`
- Modify: `frontend/angular.json`
- Modify: `frontend/package.json`

1. Add a typed `demo` flag to every environment.
2. Register the demo interceptor only when the flag is true.
3. Add `ng build --configuration=demo` without changing the normal production build.

### Task 3: Read-only demo UX

**Files:**
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.spec.ts`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.ts`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.html`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.scss`

1. Write a failing component test for the demo label, safety message, and GitHub link.
2. Add the environment-driven status rail and hide the admin navigation in demo mode.
3. Verify desktop/mobile layout, keyboard focus, and existing dashboard tests.

### Task 4: Static hosting configuration

**Files:**
- Create: `frontend/vercel.json`
- Modify: `.gitignore` if `.vercel` is not already ignored.

1. Configure Vercel to run the demo build, publish Angular's browser output, and rewrite SPA routes.
2. Build locally and inspect the output for accidental backend URLs or secrets.
3. Run frontend unit tests and lint/type/build checks.

### Task 5: Deploy and document

**Files:**
- Modify: `README.md`
- Modify: `docs/open-source-launch/copy-en.md`
- Modify: `docs/open-source-launch/copy-es.md`
- Modify: `docs/open-source-launch/launch-checklist.md`

1. Create and verify a Vercel preview deployment.
2. Promote/deploy the verified build to production.
3. Smoke-test `/`, `/dashboard/ingestion`, `/dashboard/applications`, and `/dashboard/analytics`.
4. Add the production URL to the repository README and both launch-copy documents.
5. Review the diff for generated files, secrets, unrelated changes, and inaccurate claims.
