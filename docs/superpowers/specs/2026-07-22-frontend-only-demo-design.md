# HireSense Frontend-Only Demo Design

## Goal

Publish a safe, deterministic HireSense demo on Vercel that lets visitors explore the product without a backend, credentials, uploads, or real candidate data.

## Approach

Add a dedicated Angular `demo` build configuration. In that build only, a browser-side HTTP interceptor answers the existing `/api` requests with coherent synthetic fixtures. Normal development and production builds continue to use the real backend.

The demo opens as an authenticated non-admin candidate and supports the primary evaluation journey:

1. Browse ranked jobs in Discover.
2. Inspect a job's match evidence.
3. Review a prepared application and tailored materials.
4. Explore interview preparation and analytics.

Write operations that are needed to navigate the prepared story return deterministic, precomputed results. Destructive, administrative, upload, import, email, and external-sync operations are rejected with a clear read-only-demo response.

## Data and safety

- All people, employers, roles, URLs, compensation figures, and activity are fictional.
- Demo auth exists only in memory and never accepts or stores credentials.
- The static build has no backend URL or secrets.
- External job links use non-production example URLs.
- A persistent status strip labels the experience as synthetic and read-only and links to the source repository.

## Visual direction

Preserve HireSense's existing product UI and typography. Add one signature element: a compact amber status rail above the workspace, styled like an environment indicator used in professional developer tools.

- Ink: `#172033`
- Signal amber: `#F4B740`
- Pale amber: `#FFF8E7`
- Boundary: `#E8D29A`
- Link blue: the project's existing accent token

The rail reads: `DEMO · Synthetic data · Read-only`, adds a short explanation, and includes a GitHub link. It collapses cleanly on mobile and keeps visible keyboard focus.

## Deployment

Vercel builds the Angular `demo` configuration and serves `dist/frontend/browser`. A catch-all rewrite sends client-side routes to `index.html`. The demo project is deployed separately from the real application so the public URL can never select the live API build accidentally.

## Acceptance criteria

- A fresh visitor lands inside the app without login.
- Discover, Pipeline, and Insights render useful, coherent synthetic content.
- Core prepared-detail routes render without network calls to a backend.
- The demo is visibly labeled and links to `https://github.com/StevSant/HireSense`.
- Unsupported writes explain that the public demo is read-only.
- The standard Angular build remains configured for the real API.
- Unit tests, lint/type checks, and the demo production build pass.
- A public Vercel production URL is smoke-tested, including a deep route refresh.
