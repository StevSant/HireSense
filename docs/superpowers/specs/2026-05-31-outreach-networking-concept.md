# Outreach & Networking — Concept Stub

**Date:** 2026-05-31
**Status:** ⚠️ CONCEPT — NOT yet designed. Brainstorm required before any plan. Captures the idea and open questions only.

## Idea

The genuinely missing stage of the job-hunt loop. Today HireSense covers ingest → match → apply → track → interview, but nothing helps with **reaching out**: messaging recruiters / hiring managers, warm-intro tracking, and follow-up reminders. There's already reference material in the repo (`docs/reference/message_To_apprach_recruiters.md`) that encodes the user's outreach style — a natural seed for generation.

## Why it's compelling here

- Fills a real gap rather than duplicating built features.
- Reuses the LLM provider abstraction and the profile/company-research contexts to generate tailored, on-brand outreach (the reference doc defines the voice).
- Follow-up reminders pair naturally with the tracking pipeline (a contacted role that's gone quiet).

## Rough scope (to be refined by brainstorming)

- **Outreach message generation**: given a job/company (and optionally a named contact), draft a tailored outreach message in the user's style, grounded in the profile + company research.
- **Follow-up tracking**: record that outreach was sent, when, and surface "time to follow up" nudges.
- **Warm-intro tracking** (maybe): note shared connections / referral paths per company.

## Likely integration points

- `research` (company context), `profile` (candidate background), the LLM factory (generation), `tracking` (link outreach to a tracked application + follow-up state), and the `docs/reference/message_*` style guide as a prompt seed.

## Open questions to resolve in brainstorming

1. **Generation grounding** — how much from company research vs. profile vs. the style-guide doc? Is the style guide a static prompt or user-editable?
2. **Contacts model** — do we model contacts/recruiters as first-class entities, or keep outreach attached to a tracked application?
3. **Follow-up cadence** — reminders need a scheduler; same external-cron constraint as the rest of the system (no self-scheduling). In-app nudges vs. notifications?
4. **Sending** — generate-and-copy only (user sends manually), or ever integrate an outbound channel (email/LinkedIn)? Outbound automation is high-stakes and likely out of scope initially.
5. **Where it lives** — new `outreach` bounded context, or an extension of `tracking`?

## Explicitly undecided

All of the above. Run `superpowers:brainstorming` before planning.
