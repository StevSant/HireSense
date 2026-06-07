# Identity — Real Admin Role + Account Settings — Design

**Issue:** #38 · **Replaces** the dangling `TODO(#19)` in `admin.guard.ts`.

## Context

Auth today is a single configured user (`AUTH_USERNAME`/`AUTH_PASSWORD`) with an HS256 JWT carrying
only `sub`. The backend admin seam already exists — `admin/api/dependencies.py` has
`require_admin = require_auth` (a placeholder) and both admin routers (`routes_llm_settings`,
`routes_usage`) already `Depends(require_admin)`. The frontend `adminGuard` likewise just delegates
to `isAuthenticated()` with a `TODO(#19)`. This issue makes the role real on both ends and adds a
minimal account page. The system stays single-user; the role is config-driven so a non-admin
instance is possible and the gate is genuinely exercised.

## Backend

- **Config:** `auth_role: str = "admin"` (+ `.env.example` `AUTH_ROLE=admin` with a comment: the role
  embedded in issued tokens; a single-user instance is admin by default).
- **Token:** `AuthService` gains a `role`; `_create_token` adds a `"role"` claim. `IdentityProvider`
  + `bootstrap` pass `role=settings.auth_role`. `login`/`validate_token` signatures unchanged.
- **Dependencies (`identity/api/dependencies.py`):**
  - `get_current_user` → returns the validated payload `{sub, role, ...}` (401 on invalid).
  - `require_admin` → real dependency: validates the token and raises **403** when
    `payload.get("role") != "admin"`. Export it from identity.
  - `admin/api/dependencies.py`: replace `require_admin = require_auth` with
    `from hiresense.identity.api.dependencies import require_admin` (the admin routers keep depending
    on it, now enforcing the role).
- **Endpoint:** `GET /auth/me` (auth-gated) → `MeResponse { username: str, role: str }` from the
  current-user payload.
- **Tests (integration, real app + SQLite):** issued login token contains `role`; `/auth/me` returns
  `{username, role}`; an admin-gated endpoint (e.g. `GET /admin/usage/...` or `/admin/llm-settings`)
  returns **403** with a valid non-admin token and **200/normal** with an admin token. Unit: token
  carries role; `require_admin` rejects non-admin, accepts admin.

## Frontend

- **`core/utils/role-from-token.ts`** — decode the JWT `role` claim locally (mirror
  `is-token-expired.ts`; returns `null` on missing/malformed). Client-side hint only; backend remains
  authority.
- **`AuthService`:** `role = computed(() => roleFromToken(token))`, `isAdmin = computed(() => role() === 'admin')`,
  and `me(): Observable<{ username: string; role: string }>` → `GET /auth/me`.
- **`adminGuard`:** admit only when `isAuthenticated() && isAdmin()`; an authenticated non-admin →
  redirect to `/dashboard` (not login); unauthenticated → `/login`. Remove the `TODO(#19)`; replace
  with a comment referencing this issue (#38) and the role check.
- **Account page** `pages/account/account.component.ts` (+html/scss), route `dashboard/account`,
  sidebar nav link: on init `auth.me()` → show username + a role badge + account/session info and a
  logout button; loading + error states. Read-only (password lives in env; note that inline).
- **Tests:** `role-from-token` decode; `auth.service` `isAdmin`/`role` from token; `adminGuard` admits
  admin / blocks non-admin (UrlTree to `/dashboard`); account component renders `me()` + handles error.

## Acceptance (from #38)
- Admin routes blocked for non-admin users end-to-end (backend 403 + frontend guard redirect). ✓
- TODO comment updated to reference #38. ✓
- Minimal account settings page. ✓

## Out of scope
Multi-user accounts, registration, password change at runtime, RBAC beyond admin/non-admin.
