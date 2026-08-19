# Apply-access audit — can the candidate actually apply?

**Date:** 2026-08-19
**Status:** implemented
**Trigger:** A RemoteOK listing surfaced by HireSense (AI Intern @ CertifyOS, 75% match)
sent the user to `remoteok.com/premium` — a $14.95/mo subscription page — instead of the
employer's application form.

## Problem

HireSense modelled a lot about each source (closure strategy, salary coverage, pagination,
tags) but nothing about **whether a candidate can reach the application form from the URL we
store**. A source can be excellent at listing jobs and useless for applying to them, and
nothing in the product said so. The user found out by clicking.

## Root cause for RemoteOK

RemoteOK's public API exposes two URL fields that are byte-identical:

```json
{
  "url":       "https://remoteok.com/remote-jobs/remote-ai-intern-certifyos-1135555",
  "apply_url": "https://remoteok.com/remote-jobs/remote-ai-intern-certifyos-1135555"
}
```

The employer's real application URL is never in the payload. On the job page the Apply
button is `<a href="/l/1135555">` and the JSON-LD carries `"directApply": false` — RemoteOK
deliberately keeps the destination behind its own redirector, which serves the premium
interstitial to non-subscribers.

Probed directly on 2026-08-19:

| URL | Result |
| --- | --- |
| `remoteok.com/l/1135555` | `302` → back to the job page |
| `remoteok.com/l/1135555?skip_premium=1` | `302` → back to the job page |

There is no free path to the employer link, and RemoteOK's API terms of service require
linking back to the RemoteOK URL, so routing around it is not an option either. **RemoteOK
is a pay-to-apply source.**

## Audit results — all sources

Verified 2026-08-19 by fetching a live listing per source and following the Apply control
(headless HTTP plus a real browser for the bot-blocked boards).

| Source | Apply hop | Verdict |
| --- | --- | --- |
| remoteok | `/l/<id>` → `remoteok.com/premium`, $14.95/mo | `paid_required` |
| weworkremotely | Apply → `/job-seekers/account/register` | `account_required` |
| himalayas | Apply → `himalayas.app/signup/talent` | `account_required` |
| getonboard | "Postular" → `/applications/new`, email or Google/LinkedIn/GitHub auth | `account_required` |
| linkedin | Requires a signed-in LinkedIn session | `account_required` |
| yc_jobs | Requires a Work at a Startup account | `account_required` |
| remotive | Apply button, no signup prompt | `direct` |
| themuse | "Apply on company site" | `direct` |
| dice | Records `applyUrl` in `source_metadata` | `direct` |
| hn_hiring | URLs come from the comment body → employer | `direct` |
| arbeitnow | `<listing>/apply` → `302` to the employer ATS | `direct` |
| jobicy | Job pages serve a Cloudflare challenge that does not resolve | `unknown` |
| crunchboard | `crunchboard.com/jobs.rss` → `301` → `jobboard.io` | dead source |

Direct-ATS adapters (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee,
Workday, Globant, Thoughtworks) are unaffected — they already classify as `ATS_FORM`.

## Decision

Badge, don't remove. Every source keeps ingesting: a walled listing is still useful for
discovery, and cross-source dedup already prefers tier-0 ATS listings when the same role
appears on a company's own board. What was missing was **telling the user before they
click**.

## Changes

1. **`ingestion/domain/apply_access.py`** — new `ApplyAccess` enum
   (`direct` / `account_required` / `paid_required` / `unknown`).
2. **`source_capabilities.py`** — `apply_access` and `apply_access_note` on
   `SourceCapabilities`, populated for all 20 registered sources from the table above, plus
   `source_apply_access()` / `source_apply_access_note()` lookups.
3. **`models.py`** — `NormalizedJob` gains three Pydantic computed fields:
   `apply_access`, `apply_access_note`, and `preferred_apply_url`. They are **computed, not
   persisted**: apply-access is a property of the board, not the posting, so resolving it at
   read time keeps already-ingested jobs correct and needs no migration when a board changes
   its policy.
4. **`arbeitnow_normalizer.py`** — records `source_metadata.application_url` as
   `<listing>/apply`, Arbeitnow's own hop that 302s straight to the employer's ATS. The
   listing URL stays canonical because the closure sweep probes it.
5. **Frontend** — the job detail panel and the standalone job page show a warning band above
   the actions when `apply_access` is walled, and "View Original" now opens
   `preferred_apply_url` (confirmed ATS form → board-supplied direct apply URL → listing
   page) instead of always the listing page. The job **list** carries a compact marker next
   to the source badge (`🔒` paid / `👤` free account, note in the `title`) so a page of
   results can be triaged without opening each row, and its "View" link uses
   `preferred_apply_url` too.
6. **CrunchBoard disabled by default** in `IngestionSettings.enabled_job_sources` and
   `.env.example`, with the dead feed documented in its `limitations`.

`preferred_apply_url` is the general fix for the class of bug: `source_metadata.application_url`
was already being captured by the dice, yc_jobs, and import normalizers and then ignored by
the UI.

## Follow-ups not taken

- **Jobicy is unreachable from this machine.** Re-probed 2026-08-19: the Cloudflare
  "Verificación de seguridad en curso" interstitial never resolves, and it blocks
  `jobicy.com/` itself, not just job pages — so it is a blanket block on the client or IP,
  not a per-listing gate. The v2 API keeps answering normally (`id`, `url`, `jobSlug`,
  `jobTitle`, `companyName`, `jobIndustry`, `jobType`, `jobGeo`, `jobLevel`, `pubDate`,
  descriptions) and carries **no** employer apply link, so if the page is unreachable the
  listing is unactionable — we ingest jobs nobody can apply to. Two candidate causes remain,
  and they need a human click to tell apart: Cloudflare fingerprinting the automated browser,
  or the IP/region being blocked outright. If it is the latter, jobicy should move to
  `enabled_by_default=False` like crunchboard. Left `unknown` and enabled pending that check.
- **Demoting walled sources in ranking** (pushing `remoteok` down `SOURCE_TIER`, adding a
  `?hide_walled=` filter) was considered and deferred — badging first, so the signal is
  visible before it changes ranking behaviour.
