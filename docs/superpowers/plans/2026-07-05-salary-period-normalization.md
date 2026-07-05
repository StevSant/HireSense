# Salary Period Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pay periods unambiguous — parser tracks the detected/inferred period and infers monthly for implausibly-low unlabeled figures; the Analytics pay card labels figures and offers an annual⇄monthly display toggle.

**Architecture:** Backend change is confined to `analytics/domain/salary.py` (a `period` field + a config-driven magnitude heuristic) and `MarketIntelService` (an `inferred_count` transparency signal). The frontend toggle is a pure display transform (÷12) — values stay annual on the wire.

**Tech Stack:** Python 3.13, Pydantic, pytest (backend); Angular 21 standalone + signals, Vitest (frontend).

## Global Constraints

- Run backend commands from `backend/` via `uv run python -m …` (the bare `uv run pytest` trampoline is broken on this machine).
- No hardcoded configurable values: the annual floor goes through `config/groups/` + `.env.example`.
- One class/function/constant per file where practical; every new package symbol is re-exported from its package `__init__.py`; import from the contextual package, never the implementation file.
- Backend `domain/` imports no framework packages; keep `salary.py` pure.
- Commit after each task with Conventional Commits (`type(scope): …`), scope `analytics`.

---

### Task 1: Add `SALARY_ANNUAL_FLOOR` config

**Files:**
- Modify: `backend/src/hiresense/config/groups/analytics.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: `settings.salary_annual_floor: int` (flat access on the composed `Settings`).

- [ ] **Step 1: Add the field to `AnalyticsSettings`**

In `backend/src/hiresense/config/groups/analytics.py`, add after `analytics_corpus_sample_cap`:

```python
    # --- Salary period normalization ---
    # Raw magnitude (pre-multiplier, currency-agnostic) below which an UNLABELED
    # salary figure is treated as monthly (×12) rather than annual. LATAM job
    # boards often list monthly pay with no period keyword; a bare "USD 2,500"
    # is monthly, not a 2,500/yr annual salary. Chosen below any realistic annual
    # salary so plausible annual figures are never downgraded. Only ever raises a
    # too-low unlabeled figure to monthly; labeled figures are unaffected.
    salary_annual_floor: int = 12000
```

- [ ] **Step 2: Document it in `.env.example`**

In `backend/.env.example`, under the analytics block (near `ANALYTICS_TARGET_SALARY_MIN_SAMPLE`), add:

```bash
# Raw figure below which an UNLABELED salary is read as monthly (×12) instead of
# annual. Guards against LATAM monthly postings with no period keyword being
# mistaken for annual. Set below any realistic annual salary in your target market.
SALARY_ANNUAL_FLOOR=12000
```

- [ ] **Step 3: Verify config loads**

Run: `cd backend && uv run python -c "from hiresense.config.settings import Settings; print(Settings().salary_annual_floor)"`
Expected: `12000`

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/config/groups/analytics.py backend/.env.example
git commit -m "feat(analytics): add SALARY_ANNUAL_FLOOR config for period inference"
```

---

### Task 2: `ParsedSalary.period` + magnitude heuristic in `SalaryParser`

**Files:**
- Modify: `backend/src/hiresense/analytics/domain/salary.py`
- Test: `backend/tests/unit/analytics/test_salary_parser.py`

**Interfaces:**
- Consumes: `settings.salary_annual_floor` (injected via constructor).
- Produces:
  - `ParsedSalary` gains `period: str` — one of `"annual" | "monthly" | "hourly" | "unknown"`.
  - `SalaryParser(annual_floor: int = _DEFAULT_ANNUAL_FLOOR)` — new optional constructor arg; `SalaryParser()` still valid (existing tests unchanged).
  - `parse(raw)` return contract unchanged except the new `period` field.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/unit/analytics/test_salary_parser.py`:

```python
def test_labeled_monthly_sets_period_and_annualizes():
    r = SalaryParser().parse("USD 2300-2500/mo")
    assert r is not None
    assert r.period == "monthly"
    assert r.min_annual == 27600  # 2300 * 12
    assert r.max_annual == 30000  # 2500 * 12


def test_labeled_hourly_sets_period():
    r = SalaryParser().parse("$50/hour")
    assert r is not None
    assert r.period == "hourly"
    assert r.min_annual == 104000  # 50 * 2080


def test_unlabeled_low_figure_inferred_monthly():
    # Below the floor, no period keyword -> inferred monthly.
    r = SalaryParser(annual_floor=12000).parse("USD 2500")
    assert r is not None
    assert r.period == "monthly"
    assert r.min_annual == 30000  # 2500 * 12


def test_unlabeled_plausible_figure_is_unknown_annual():
    # Above the floor, no keyword -> assumed annual, flagged unknown.
    r = SalaryParser(annual_floor=12000).parse("USD 90,000")
    assert r is not None
    assert r.period == "unknown"
    assert r.min_annual == 90000
    assert r.max_annual == 90000


def test_unlabeled_range_uses_min_for_floor_decision():
    # A range whose LOWEST figure is below the floor is treated as monthly.
    r = SalaryParser(annual_floor=12000).parse("USD 2500-2800")
    assert r is not None
    assert r.period == "monthly"
    assert r.min_annual == 30000  # 2500 * 12
    assert r.max_annual == 33600  # 2800 * 12
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/analytics/test_salary_parser.py -v`
Expected: FAIL — `ParsedSalary` has no `period`; `SalaryParser` takes no `annual_floor`.

- [ ] **Step 3: Implement**

Rewrite `backend/src/hiresense/analytics/domain/salary.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "eur": "EUR", "gbp": "GBP"}
_HOURS_PER_YEAR = 2080
_MONTHS_PER_YEAR = 12
# Fallback floor when no config-driven value is injected. The app path injects
# settings.salary_annual_floor via bootstrap; this default only backs bare
# SalaryParser() construction (e.g. in tests).
_DEFAULT_ANNUAL_FLOOR = 12000
# A number with optional thousands separators and an optional k/m suffix.
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kKmM])?"


@dataclass(frozen=True)
class ParsedSalary:
    currency: str
    min_annual: int
    max_annual: int
    # Detected (or inferred) SOURCE period. "unknown" == no keyword found and the
    # figure was plausible for annual, so annual was assumed.
    period: str


def _detect_currency(text: str) -> str | None:
    for token, code in _CURRENCY.items():
        if token in text.lower() if token.isalpha() else token in text:
            return code
    return None


def _to_number(value: str, suffix: str | None) -> float:
    n = float(value.replace(",", ""))
    if suffix in ("k", "K"):
        n *= 1000
    elif suffix in ("m", "M"):
        n *= 1_000_000
    return n


def _keyword_period(text: str) -> str | None:
    t = text.lower()
    if "hour" in t or "/hr" in t or "/h" in t:
        return "hourly"
    if "month" in t or "/mo" in t:
        return "monthly"
    return None


class SalaryParser:
    """Best-effort free-text salary parser. Returns None on unparseable input.

    Handles $/€/£ (+ usd/eur/gbp), comma thousands, `k`/`m` suffixes, single
    value or range, and hourly/monthly→annual normalization. Records the source
    `period`. When no period keyword is present, an implausibly-low figure (below
    `annual_floor`) is inferred as monthly; an otherwise-plausible figure is
    assumed annual and flagged `"unknown"`. Lossy by design.
    """

    def __init__(self, annual_floor: int = _DEFAULT_ANNUAL_FLOOR) -> None:
        self._annual_floor = annual_floor

    def parse(self, raw: str | None) -> ParsedSalary | None:
        if not raw or not raw.strip():
            return None
        currency = _detect_currency(raw)
        if currency is None:
            return None
        raw_numbers = [_to_number(v, k) for v, k in re.findall(_NUM, raw)]
        raw_numbers = [n for n in raw_numbers if n > 0]
        if not raw_numbers:
            return None

        keyword = _keyword_period(raw)
        if keyword == "hourly":
            period, mult = "hourly", _HOURS_PER_YEAR
        elif keyword == "monthly":
            period, mult = "monthly", _MONTHS_PER_YEAR
        elif min(raw_numbers) < self._annual_floor:
            period, mult = "monthly", _MONTHS_PER_YEAR
        else:
            period, mult = "unknown", 1

        annual = sorted(int(round(n * mult)) for n in raw_numbers)
        return ParsedSalary(
            currency=currency, min_annual=annual[0], max_annual=annual[-1], period=period,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/analytics/test_salary_parser.py -v`
Expected: PASS (new tests + existing ones — existing tests construct `SalaryParser()` and don't assert `period`, so they remain green).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/salary.py backend/tests/unit/analytics/test_salary_parser.py
git commit -m "feat(analytics): parse salary period + infer monthly for low unlabeled figures"
```

---

### Task 3: Wire the config floor through bootstrap

**Files:**
- Modify: `backend/src/hiresense/bootstrap/analytics.py:41`

**Interfaces:**
- Consumes: `s.salary_annual_floor`, `SalaryParser(annual_floor=…)`.

- [ ] **Step 1: Inject the floor**

In `backend/src/hiresense/bootstrap/analytics.py`, change line 41:

```python
    salary_parser = SalaryParser(annual_floor=s.salary_annual_floor)
```

- [ ] **Step 2: Verify the app boots and analytics tests pass**

Run: `cd backend && uv run python -m pytest tests/unit/analytics tests/integration/test_analytics_endpoints.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/bootstrap/analytics.py
git commit -m "feat(analytics): inject SALARY_ANNUAL_FLOOR into SalaryParser"
```

---

### Task 4: `SalaryDistribution.inferred_count` transparency signal

**Files:**
- Modify: `backend/src/hiresense/analytics/domain/market_service.py`
- Test: `backend/tests/unit/analytics/test_market_service.py`

**Interfaces:**
- Produces: `SalaryDistribution.inferred_count: int` — count of parsed postings whose `period` was `"monthly"`-by-inference or `"unknown"` (i.e. basis was inferred/assumed, not stated). Counted for the dominant currency only.

- [ ] **Step 1: Write failing test**

Add to `backend/tests/unit/analytics/test_market_service.py` (adapt the fake corpus's salary strings — inspect the existing `_FakeCorpus` in that file and set `open_salary_strings` to return a mix). Example test:

```python
def test_salary_distribution_counts_inferred_basis(monkeypatch):
    # Two labeled ("/mo") + one unlabeled-low (inferred monthly) + one unlabeled-high (unknown).
    from hiresense.analytics.domain import MarketIntelService, SkillNormalizer, SalaryParser

    class _Corpus:
        def open_salary_strings(self):
            return (["USD 3000/mo", "USD 3500/mo", "USD 2500", "USD 90,000"], 4)
        def remote_modality_counts(self): return {}
        def open_skill_lists(self): return []
        def posting_dates(self): return []

    svc = MarketIntelService(_Corpus(), SkillNormalizer(), SalaryParser(annual_floor=12000))
    dist = svc._salary_distribution()
    # "USD 2500" (inferred monthly) + "USD 90,000" (unknown) == 2 inferred-basis.
    assert dist.inferred_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/analytics/test_market_service.py::test_salary_distribution_counts_inferred_basis -v`
Expected: FAIL — `SalaryDistribution` has no `inferred_count`.

- [ ] **Step 3: Implement**

In `backend/src/hiresense/analytics/domain/market_service.py`:

1. Add the field to `SalaryDistribution` (after `disclosed_pct`):

```python
    # Postings (dominant currency) whose period was inferred (low unlabeled →
    # monthly) or assumed (unlabeled → annual). Lets the UI caveat the band.
    inferred_count: int = 0
```

2. In `_salary_distribution`, track inferred basis per currency alongside `midpoints`/`bounds`:

```python
        inferred: dict[str, int] = {}
```

   Inside the parse loop, after computing `parsed`:

```python
            if parsed.period in ("monthly", "hourly", "unknown") and self._is_inferred(parsed):
                inferred[parsed.currency] = inferred.get(parsed.currency, 0) + 1
```

   Replace that with the simpler, explicit rule (no helper needed) — count only inferred/assumed basis, i.e. periods that were NOT from an explicit keyword. Since the parser doesn't expose "was it a keyword", treat `"unknown"` and inferred-`"monthly"` as the inferred set. To distinguish keyword-monthly from inferred-monthly without extra state, count `period == "unknown"` plus monthly figures whose raw magnitude was below the floor is not available here. **Simplify the contract:** count `period == "unknown"` only as "assumed", and expose it as `inferred_count`. Update the test accordingly (see note below).

   **Final implementation (authoritative):** count `period == "unknown"`:

```python
            if parsed.period == "unknown":
                inferred[parsed.currency] = inferred.get(parsed.currency, 0) + 1
```

3. Add `inferred_count=inferred.get(dominant, 0)` to the non-empty `SalaryDistribution(...)` return; the empty-branch return keeps the default `inferred_count=0`.

   **Adjust the Step 1 test** to match this authoritative contract: with inputs `["USD 3000/mo", "USD 3500/mo", "USD 2500", "USD 90,000"]`, only `"USD 90,000"` is `"unknown"`, so `assert dist.inferred_count == 1`. Update the assertion before running.

> Rationale for the simplification: distinguishing keyword-monthly from inferred-monthly requires the parser to expose whether a keyword matched. That is not worth a wider `ParsedSalary` contract for a UI footnote. "Assumed annual" (`unknown`) is the honest, useful caveat; inferred-monthly figures are already correctly annualized and need no caveat.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/analytics/test_market_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/market_service.py backend/tests/unit/analytics/test_market_service.py
git commit -m "feat(analytics): expose inferred-basis salary count in distribution"
```

---

### Task 5: Frontend pay-period util

**Files:**
- Create: `frontend/src/app/core/utils/pay-period.ts`
- Test: `frontend/src/app/core/utils/pay-period.spec.ts`

**Interfaces:**
- Produces:
  - `type PayPeriod = 'annual' | 'monthly'`
  - `toPeriod(annual: number | null, period: PayPeriod): number | null`
  - `periodUnit(period: PayPeriod): string`

- [ ] **Step 1: Write failing test**

Create `frontend/src/app/core/utils/pay-period.spec.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { toPeriod, periodUnit } from './pay-period';

describe('pay-period', () => {
  it('returns the annual value unchanged for annual', () => {
    expect(toPeriod(31200, 'annual')).toBe(31200);
  });

  it('divides by 12 (rounded) for monthly', () => {
    expect(toPeriod(31200, 'monthly')).toBe(2600);
  });

  it('passes null through', () => {
    expect(toPeriod(null, 'monthly')).toBeNull();
  });

  it('labels the unit', () => {
    expect(periodUnit('annual')).toBe('/year');
    expect(periodUnit('monthly')).toBe('/mo');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/pay-period.spec.ts"`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/app/core/utils/pay-period.ts`:

```typescript
export type PayPeriod = 'annual' | 'monthly';

const MONTHS_PER_YEAR = 12;

/** Convert an annual figure to the chosen display period. Display-only. */
export function toPeriod(annual: number | null, period: PayPeriod): number | null {
  if (annual === null) return null;
  return period === 'monthly' ? Math.round(annual / MONTHS_PER_YEAR) : annual;
}

export function periodUnit(period: PayPeriod): string {
  return period === 'monthly' ? '/mo' : '/year';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/pay-period.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/utils/pay-period.ts frontend/src/app/core/utils/pay-period.spec.ts
git commit -m "feat(analytics): add pay-period display conversion util"
```

---

### Task 6: `SalaryBandComponent` — period-aware figures + unit label

**Files:**
- Modify: `frontend/src/app/pages/analytics/components/salary-band/salary-band.component.ts`
- Modify: `frontend/src/app/pages/analytics/components/salary-band/salary-band.component.html`
- Test: `frontend/src/app/pages/analytics/components/salary-band/salary-band.component.spec.ts` (create if absent)

**Interfaces:**
- Consumes: `toPeriod`, `periodUnit`, `PayPeriod`.
- Produces: new `period = input<PayPeriod>('annual')`; the rendered band numbers reflect `period`.

- [ ] **Step 1: Write failing test**

Create/extend `salary-band.component.spec.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { SalaryBandComponent } from './salary-band.component';

const target = {
  insufficient_data: false, currency: 'USD',
  p25_annual: 27600, median_annual: 31200, p75_annual: 39000, sample_size: 21,
};

describe('SalaryBandComponent', () => {
  it('shows monthly figures when period is monthly', () => {
    const fixture = TestBed.createComponent(SalaryBandComponent);
    fixture.componentRef.setInput('target', target);
    fixture.componentRef.setInput('period', 'monthly');
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('2,600'); // 31200 / 12
    expect(text).not.toContain('31,200');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/salary-band.component.spec.ts"`
Expected: FAIL — `period` input doesn't exist / figures still annual.

- [ ] **Step 3: Implement**

In `salary-band.component.ts`, add imports and the input, and make `fmt` period-aware:

```typescript
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TargetSalary } from '../../models/target-salary.model';
import { PayPeriod, periodUnit, toPeriod } from '../../../../core/utils/pay-period';
```

Add inside the class:

```typescript
  period = input<PayPeriod>('annual');
  unit = computed(() => periodUnit(this.period()));
```

Change `fmt`:

```typescript
  fmt(v: number | null): string {
    const shown = toPeriod(v, this.period());
    return shown === null ? '—' : shown.toLocaleString('en-US');
  }
```

In `salary-band.component.html`, append the unit to the median line — change line 15-19 caps block to include the unit on "Median" (or add next to the numbers). Minimal change: update the `band-numbers` block:

```html
  <div class="band-numbers">
    <span>{{ target().currency }} {{ fmt(target().p25_annual) }}</span>
    <strong>{{ fmt(target().median_annual) }} <span class="band-unit">{{ unit() }}</span></strong>
    <span>{{ fmt(target().p75_annual) }}</span>
  </div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/salary-band.component.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/analytics/components/salary-band/
git commit -m "feat(analytics): make salary band period-aware with unit label"
```

---

### Task 7: `CompBenchmarkComponent` — thread period through the pay card

**Files:**
- Modify: `frontend/src/app/pages/analytics/components/comp-benchmark/comp-benchmark.component.ts`
- Modify: `frontend/src/app/pages/analytics/components/comp-benchmark/comp-benchmark.component.html`
- Test: `frontend/src/app/pages/analytics/components/comp-benchmark/comp-benchmark.component.spec.ts` (create if absent)

**Interfaces:**
- Consumes: `PayPeriod`, `toPeriod`, `periodUnit`, `SalaryBandComponent` `period` input (Task 6).
- Produces: `period = input<PayPeriod>('annual')` forwarded to `<app-salary-band>`; all money figures + the "/ year" suffix reflect `period`.

- [ ] **Step 1: Write failing test**

Create `comp-benchmark.component.spec.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { CompBenchmarkComponent } from './comp-benchmark.component';

const comp = {
  insufficient_data: false, currency: 'USD',
  p25_annual: 27600, median_annual: 31200, p75_annual: 39000, sample_size: 21,
  by_seniority: [], your_median_annual: 15000, your_sample_size: 3,
  ask_min_annual: 31200, ask_max_annual: 39000,
};

describe('CompBenchmarkComponent', () => {
  it('shows monthly ask range and /mo unit when monthly', () => {
    const fixture = TestBed.createComponent(CompBenchmarkComponent);
    fixture.componentRef.setInput('comp', comp);
    fixture.componentRef.setInput('period', 'monthly');
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('2,600'); // 31200 / 12 (ask_min)
    expect(text).toContain('/mo');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/comp-benchmark.component.spec.ts"`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `comp-benchmark.component.ts`, add imports + input + period-aware `fmt` + `unit`:

```typescript
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CompBenchmark } from '../../models/comp-benchmark.model';
import { BarRow } from '../../models/bar-row.model';
import { SalaryBandComponent } from '../salary-band/salary-band.component';
import { BarChartComponent } from '../bar-chart/bar-chart.component';
import { PayPeriod, periodUnit, toPeriod } from '../../../../core/utils/pay-period';
```

Add to the class:

```typescript
  period = input<PayPeriod>('annual');
  unit = computed(() => periodUnit(this.period()));
```

Change `fmt`:

```typescript
  fmt(v: number | null): string {
    const shown = toPeriod(v, this.period());
    return shown === null ? '—' : shown.toLocaleString('en-US');
  }
```

In `comp-benchmark.component.html`:
- Line 6: `<app-salary-band [target]="comp()" [period]="period()" />`
- Line 12: replace `/ year — aim…` with `{{ unit() }} — aim between the market median and the top quartile.`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/comp-benchmark.component.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/analytics/components/comp-benchmark/
git commit -m "feat(analytics): thread pay period through comp-benchmark card"
```

---

### Task 8: `AnalyticsComponent` — toggle control, KPI period, basis footnote

**Files:**
- Modify: `frontend/src/app/pages/analytics/analytics.component.ts`
- Modify: `frontend/src/app/pages/analytics/analytics.component.html`
- Modify: `frontend/src/app/pages/analytics/models/market-intel.model.ts`
- Test: `frontend/src/app/pages/analytics/analytics.component.spec.ts`

**Interfaces:**
- Consumes: `PayPeriod`, `toPeriod`, `periodUnit`, `CompBenchmarkComponent` `period` input (Task 7).
- Produces: `payPeriod` signal + `setPayPeriod(p)`; KPI "Target median" reflects the period; a footnote when `salary_distribution.inferred_count > 0`.

- [ ] **Step 1: Add `inferred_count` to the frontend model**

In `frontend/src/app/pages/analytics/models/market-intel.model.ts`, add to `SalaryDistribution`:

```typescript
  inferred_count: number;
```

- [ ] **Step 2: Write failing test**

Add to `analytics.component.spec.ts` (follow the file's existing harness/mocks). A behavior test for the toggle:

```typescript
it('toggling to monthly re-labels the target-median KPI', async () => {
  // ...arrange with the file's existing mocked AnalyticsService returning a comp
  //    with median_annual: 31200, currency 'USD'...
  component.setPayPeriod('monthly');
  fixture.detectChanges();
  const median = component.kpis().find((k) => k.label === 'Target median');
  expect(median?.value).toContain('2,600'); // 31200 / 12
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/analytics.component.spec.ts"`
Expected: FAIL — `setPayPeriod` doesn't exist / KPI still annual.

- [ ] **Step 4: Implement**

In `analytics.component.ts`:

Add import:

```typescript
import { PayPeriod, periodUnit, toPeriod } from '../../core/utils/pay-period';
```

Add the `CompBenchmarkComponent` is already imported. Add state + setter to the class:

```typescript
  payPeriod = signal<PayPeriod>('annual');
  setPayPeriod(p: PayPeriod): void { this.payPeriod.set(p); }
```

In `kpis()`, change the "Target median" tile to use the period:

```typescript
      {
        label: 'Target median',
        value: compReady
          ? `${c!.currency ?? ''} ${toPeriod(c!.median_annual, this.payPeriod())!.toLocaleString('en-US')} ${periodUnit(this.payPeriod())}`.trim()
          : '—',
        hint: compReady ? `across ${c!.sample_size} matched roles` : 'for your profile',
      },
```

In `analytics.component.html`, Pay card (lines 13-18), add a toggle in the card header and pass the period:

```html
    <section class="analytics-card">
      <div class="card-head">
        <h2 class="card-title">Pay — your market band</h2>
        <div class="period-toggle" role="group" aria-label="Pay period">
          <button type="button" [class.active]="payPeriod() === 'annual'" (click)="setPayPeriod('annual')">Annual</button>
          <button type="button" [class.active]="payPeriod() === 'monthly'" (click)="setPayPeriod('monthly')">Monthly</button>
        </div>
      </div>
      @if (compError()) { <p class="section-error">Couldn't load compensation.</p> }
      @else if (comp(); as c) { <app-comp-benchmark [comp]="c" [period]="payPeriod()" /> }
      @else { <p class="section-loading">Loading…</p> }
    </section>
```

In the Market-context salary block (after line 106), add the basis footnote:

```html
          @if (m.salary_distribution.inferred_count > 0) {
            <p class="salary-basis-note">Some postings' period was inferred (annual assumed where unstated).</p>
          }
```

Add minimal styles to `analytics.component.scss` for `.card-head` (flex, space-between), `.period-toggle button` (+ `.active`), and `.salary-basis-note` (muted, small). Match existing card typography.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- --include "**/analytics.component.spec.ts"`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

Run: `cd frontend && npx ng lint`
Expected: no errors in changed files.

```bash
git add frontend/src/app/pages/analytics/
git commit -m "feat(analytics): annual/monthly pay toggle, period-aware KPI, inferred-basis note"
```

---

## Self-Review

- **Spec coverage:** `period` field (Task 2 ✓), magnitude heuristic (Task 2 ✓), config floor (Tasks 1,3 ✓), `inferred_count` transparency (Task 4 ✓), `/year` labels (Tasks 6,7 ✓), annual⇄monthly toggle across band/median/ask/pipeline + KPI (Tasks 6,7,8 ✓), basis footnote (Task 8 ✓). Median-by-seniority renders no absolute money figures (bar rows show % + sample size), so it needs no conversion — noted here so the omission is intentional, not a gap.
- **Placeholder scan:** none — every code step has concrete code. Task 4's simplification is spelled out with the authoritative implementation and the test adjustment.
- **Type consistency:** `PayPeriod`, `toPeriod`, `periodUnit` names consistent across Tasks 5-8; `period` input name consistent on salary-band and comp-benchmark; `inferred_count` consistent backend (Task 4) ↔ frontend model (Task 8).
