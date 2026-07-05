# Salary period: labels, toggle, and complete normalization — design

**Date:** 2026-07-05
**Status:** Specced

## Problem

The Analytics **Pay — your market band** card shows figures (`USD 27,600 …
31,200 … 39,000`) with no stated period. Users can't tell whether that's annual
or monthly. The underlying values *are* annual — `SalaryParser` normalizes
hourly (×2080) and monthly (×12) to annual, and GetOnBoard postings are labeled
`/mo` so they convert correctly (band low `27,600 = 2,300 × 12`). But:

1. **The UI never states the period** (only the "Suggested ask" line says
   "/year"), so the numbers read as ambiguous.
2. **Unlabeled figures silently default to annual.** A source that emits a bare
   `USD 2,500` with no period keyword is treated as `2,500/year` — an obvious
   mis-normalization for what is almost certainly a monthly LATAM salary.

## Goal

Make pay periods unambiguous end to end:

1. Track the *detected source period* per parsed salary, not just the annual
   value.
2. Infer monthly for unlabeled implausibly-low figures (magnitude heuristic).
3. Label the band/median as annual and add an **annual ⇄ monthly** display
   toggle across the pay card.

## Architecture

Backend change is confined to `analytics/domain/salary.py` and the schema that
carries its output; the toggle is a frontend display transform (values stay
annual on the wire).

### Backend

**1. `ParsedSalary` gains a `period` field.**

```
period: Literal['annual', 'monthly', 'hourly', 'unknown']
```

`min_annual` / `max_annual` remain the normalized annual values. `period` records
the *source* period that was detected (or inferred), for transparency — not a
second unit.

**2. Period detection + magnitude heuristic in `SalaryParser.parse`.**

- Explicit keyword found (`hour`/`/hr`/`/h`, `month`/`/mo`) → that period, apply
  its multiplier (unchanged behavior).
- No keyword found:
  - If the raw figure(s) sit below a configurable annual floor
    (`SALARY_ANNUAL_FLOOR`, e.g. a value no plausible annual salary falls under),
    treat as **monthly** (×12), `period = 'monthly'` (inferred).
  - Otherwise assume annual (×1), `period = 'unknown'` (assumed annual) — so the
    UI/aggregation can flag that the basis was assumed rather than stated.

The floor is read from config, not hardcoded, and applied per-currency-agnostic
raw magnitude (before multiplication). The heuristic only ever *raises* a
too-low figure to monthly; it never downgrades a plausible annual figure.

**3. Aggregation transparency (`MarketIntelService._salary_distribution`).**

`SalaryDistribution` gains a small transparency signal so the UI can note when
the band includes inferred/assumed-basis figures — e.g. `inferred_count`
(postings whose period was inferred or assumed). Existing fields unchanged;
values remain annual.

### Frontend (`pages/analytics/`)

1. **Period labels.** The market band, target median, suggested ask, and
   median-by-seniority are explicitly labeled `/year` (or `/mo` when the toggle
   is on).
2. **Annual ⇄ Monthly toggle.** A small control on the pay card. It is a pure
   display transform: monthly = `round(annual / 12)`. It applies to every money
   figure in the pay card (band min/median/max, target median, suggested-ask
   range, pipeline-vs-market figures, median-by-seniority). The chosen mode is
   held in a component signal; annual is the default.
3. **Basis note.** When the distribution reports inferred/assumed figures, show a
   subtle footnote (e.g. "some postings' period was inferred") so the band's
   caveat is visible.

No new endpoint; the toggle needs no round-trip since values are already annual.

## Config additions

- `SALARY_ANNUAL_FLOOR` — the raw magnitude below which an unlabeled figure is
  treated as monthly. Added to the matching `config/groups/` group + documented
  in `.env.example`.

## Testing

- **Parser (unit):** labeled `/mo` → monthly, ×12 (regression); labeled hourly →
  hourly, ×2080; unlabeled low figure → monthly inferred; unlabeled plausible
  figure → unknown/assumed annual; `period` set correctly in each case; floor
  read from config.
- **Aggregation (unit):** `inferred_count` reflects inferred/assumed postings;
  annual values unchanged for labeled inputs.
- **Frontend (Vitest):** toggle switches all pay figures between `/year` and
  `/mo` (÷12) and updates labels; basis footnote shows only when inferred figures
  are present.

## Decisions & limitations

- **Values on the wire stay annual.** Monthly is display-only, so the toggle
  can't drift from the source of truth.
- **The magnitude heuristic is a heuristic.** It can misclassify a genuinely
  low-paid annual role, but the floor is chosen conservatively (below any
  realistic annual salary for the target market) so false positives are rare;
  `period='unknown'` keeps the assumed-annual case honest rather than silently
  authoritative.
- **Currency-agnostic floor.** A single raw-magnitude floor is a simplification;
  per-currency floors are out of scope (the dominant currency is USD-like in
  practice).
