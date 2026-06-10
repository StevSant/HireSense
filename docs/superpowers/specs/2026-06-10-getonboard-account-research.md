# GetOnBoard Account Sync — Research Note (Phase 6: DROPPED)

**Date:** 2026-06-10
**Verdict:** NOT FEASIBLE — feature dropped per the external-sources spec's Part C gate.

## Question

Can HireSense auto-sync the candidate's own GetOnBoard application statuses into the
tracking module via an authenticated API?

## Findings (high confidence)

- GetOnBoard's private API is **explicitly company/employer-only**: "This version is
  exclusive for companies with an active subscription to any of our plans" (user
  manual). API keys exist only in company dashboards.
- The private resource set (confirmed via the official `getonbrd/getonbrd-ruby`
  client) is entirely ATS-facing: Job, Process, Application (applications RECEIVED by
  the employer), Professional, Phase, Message, Note, Answer, Webhook. There is **no**
  `/me`, `/my-applications`, saved-jobs, or any candidate-scoped endpoint.
- Webhooks: companies get 5 events (job/application lifecycle); professionals get
  exactly ONE — "a job matches your profile" (a recommendation push). No
  application-status event exists for candidates.

Sources: getonbrd.com/user-manual/get-on-board-s-api,
getonbrd.com/help/what-can-i-do-with-get-on-board-s-api,
github.com/getonbrd/getonbrd-ruby,
getonbrd.com/help/what-webhook-events-does-get-on-board-send.

## What would change the verdict

A candidate-scoped token + `GET /me/applications`, or a professional webhook for
application state changes. Neither exists today. Definitive re-test: log into a
professional account → Settings → check for an API key field.

## Alternative (not pursued)

GetOnBoard emails candidates on application events; parsing those (Gmail/IMAP) could
approximate status sync without API cooperation. Fragile (format-dependent) and out of
scope — revisit only if status sync becomes a priority.

## Disposition

Part C of `2026-06-09-external-sources-integration-design.md` is closed as dropped.
Manual status tracking (the existing tracking module) remains the GetOnBoard path.
