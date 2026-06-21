# HireSense Autopilot — Initiative Roadmap

**Date:** 2026-06-21
**Status:** Active — Phase 1 in design
**Theme:** Automate the most of the job hunt that can be automated.

## Vision

The hunt runs itself on a cadence and hands the user a review queue. Guiding
principle across every phase:

> **Automate the gathering and drafting; gate the outbound actions behind
> explicit approval.** Sending outreach or submitting an application is
> high-stakes and irreversible — those stay one-click-confirm, never zero-click.
> Everything *up to* the send can be fully autonomous.

## Why now

All previously planned backlog work has shipped (no open GitHub issues). The
single biggest structural gap is that **nothing self-schedules**: every
recurring action (ingestion fetch, revalidation sweep, autohunt digest, outreach
follow-up) is a manual `POST` that requires an external cron the user must wire
up and maintain. The capabilities exist; the automation that drives them does
not.

## Phases (each its own spec → plan → implementation cycle)

| Phase | Sub-project | Depends on | Rationale |
|------|-------------|-----------|-----------|
| **1** | **Scheduler foundation** | — | Load-bearing. Lets the app self-drive existing endpoints on a cadence. Nothing else self-runs without it. |
| **2** | **Delivery / notifications** | 1 | Once digests run on a schedule, push them to the user (email / web push). Closes the "did anything happen?" loop. |
| **3** | **Inbound email → auto-tracking** | — (parallel-able) | Uses the connected Gmail to parse rejection / interview-invite emails and auto-update the tracking board. Independent of the scheduler. |
| **4** | **End-to-end autopilot pipeline** | 1, 2 | Chain scoring → auto-draft CV / cover letter / outreach for top-N → review queue. |
| **5** | **Outbound automation** | 4 | Apply-assist prefill / handoff + outreach follow-up sequences. The gated "send" layer. |

Each phase ships independently and de-risks the next.

## Notes

- Phase 1 deliberately **reverses** the prior "external cron only, app never
  self-schedules" decision recorded in the job-lifecycle notes. This is an
  intentional architectural shift, signed off as part of this initiative.
- Phase 3 can run in parallel with Phase 1/2 since it does not depend on the
  scheduler.

## Links

- Phase 1 design: [`2026-06-21-scheduler-foundation-design.md`](./2026-06-21-scheduler-foundation-design.md)
