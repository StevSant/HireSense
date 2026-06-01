# Analytics Phase 2 — Backend `analytics` Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only `analytics` bounded context exposing four endpoints — `GET /analytics/funnel`, `/market`, `/skill-gap`, `/target-salary` — computed on the fly from tracking status history, the ingested-job corpus, the profile, and the vector store, with a short TTL cache on the heavy results.

**Architecture:** Pure helpers (`SalaryParser`, `SkillNormalizer`) + four query services (`FunnelService`, `MarketIntelService`, `SkillGapService`, `TargetSalaryService`) reading through a `CorpusAnalyticsRepository` (raw aggregation SQL over `ingested_jobs`) and tracking's `StatusHistoryReadPort`. A `TtlCache` wraps the salary distribution + target band. Wired as a new context with provider/dependencies/router, built after tracking + profile in `create_app()`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (sync session factory + raw `text()` aggregation), Pydantic v2, pytest (`asyncio_mode=auto`), `uv`.

**Spec:** `docs/superpowers/specs/2026-05-31-market-analytics-design.md` (§Architecture.2). Phase 1 (status-history table + `StatusHistoryReadPort`) is merged. Phase 3 (frontend) is a separate plan.

**Tooling (this machine):** pytest = `uv run python -m pytest ...` (NOT bare); run from `backend/`. Ruff: `uv run python -m ruff check <paths>`.

**Verified integration facts:**
- Vector store: `await vector_store.search(query_embedding: list[float], *, top_k=10, filters=None) -> list[ScoredResult]` where `ScoredResult{ id: str, score: float, metadata: dict }`. `vector_store` is `None` when provider ≠ pgvector.
- Embedding: `await infra.embedding.embed(texts: list[str]) -> list[list[float]]` (async). Profile text composed as `f"{' '.join(skills)}\n{summary}".strip()` (mirror `SemanticPreRanker._get_profile_embedding`).
- Profile: `ProfileService.get_for_language(language) -> ProfileLanguageView | None`; `ProfileLanguageView{language, summary: str, skills: list[str], raw_tex}` (frozen dataclass).
- Tracking history: `StatusHistoryReadPort.list_history() -> list[StatusTransition]` / `history_for(application_id) -> list[StatusTransition]`; `StatusTransition{id, application_id, from_status: str|None, to_status: str, changed_at: datetime|None}`. Implemented by `TrackingRepository`.
- Corpus table `ingested_jobs`: columns include `skills` (JSON list), `remote_modality` (str|None), `salary_range` (str|None, free text), `posted_date` (timestamptz|None), `status` (str: open/closed), `id`, `fetched_at`.
- API pattern (mirror `preference/api/`): `provider.py` holds the service; `dependencies.py` reads `request.app.state.analytics.get_analytics_service()`; `routes.py` defines `router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_auth)])`; `__init__.py` re-exports `router`.
- Bootstrap returns a frozen `AnalyticsBuild(provider, service)`; `build_analytics(infra, profile_service, status_history_read)` wired in `main.create_app()` after tracking + profile.
- Config block ends after `preference_explanation_enabled` (line ~215 in `config.py`).
- Integration test pattern: in-memory SQLite + `StaticPool`, `Base.metadata.create_all`, override `require_auth` → `"test-user"` and the service dependency, `AsyncClient(transport=ASGITransport(app=app))`.

---

## File Structure

**Create (domain — `backend/src/hiresense/analytics/domain/`):**
- `salary.py` — `ParsedSalary` value + `SalaryParser`.
- `skill_normalizer.py` — `SkillNormalizer`.
- `funnel_service.py` — `FunnelService` + its result models (`FunnelStage`, `FunnelMetrics`).
- `market_service.py` — `MarketIntelService` + result models (`SkillCount`, `RemoteMix`, `TrendPoint`, `SalaryDistribution`, `MarketIntel`).
- `skill_gap_service.py` — `SkillGapService` + `SkillGap`/`SkillGapItem`.
- `target_salary_service.py` — `TargetSalaryService` + `TargetSalary`.
- `ttl_cache.py` — `TtlCache`.
- `__init__.py` — re-exports.

**Create (infrastructure — `backend/src/hiresense/analytics/infrastructure/`):**
- `corpus_repository.py` — `CorpusAnalyticsRepository` (raw aggregation over `ingested_jobs`).
- `__init__.py` — re-export.

**Create (api — `backend/src/hiresense/analytics/api/`):**
- `schemas.py`, `provider.py`, `dependencies.py`, `routes.py`, `__init__.py`.

**Create (`backend/src/hiresense/analytics/__init__.py`).**

**Create bootstrap:** `backend/src/hiresense/bootstrap/analytics.py`.

**Modify:**
- `backend/src/hiresense/config.py` + `backend/.env.example` — analytics settings.
- `backend/src/hiresense/bootstrap/tracking.py` — expose the repo as `status_history_read` on `TrackingBuild`.
- `backend/src/hiresense/bootstrap/__init__.py` — export `build_analytics`, `AnalyticsBuild`.
- `backend/src/hiresense/main.py` — build + register analytics.

**Tests:** unit per domain unit under `backend/tests/unit/analytics/`; integration `backend/tests/integration/test_analytics_endpoints.py`.

> The `clamp`/sort note from Phase-1 review: history rows share `changed_at` resolution; `FunnelService` must treat the **set** of statuses reached per app (not rely on strict intra-timestamp ordering) and compute time-in-stage from min/max `changed_at` per (app, stage).

---

## Task 1: Analytics settings

**Files:** Modify `backend/src/hiresense/config.py`, `backend/.env.example`.

- [ ] **Step 1: Add settings** after the `preference_explanation_enabled` line in `config.py`:

```python
    # --- Analytics dashboard (read-only corpus/funnel aggregation) ---
    # TTL (seconds) for the heavy on-read results (salary distribution, target band).
    analytics_cache_ttl_seconds: int = 300
    # Target-salary band: how many profile-similar jobs to consider, and the
    # minimum parseable-salaried matches required before reporting a band.
    analytics_target_salary_top_k: int = 50
    analytics_target_salary_min_sample: int = 5
```

- [ ] **Step 2: Mirror in `.env.example`** (after the preference block):

```
# --- Analytics dashboard ---
ANALYTICS_CACHE_TTL_SECONDS=300
ANALYTICS_TARGET_SALARY_TOP_K=50
ANALYTICS_TARGET_SALARY_MIN_SAMPLE=5
```

- [ ] **Step 3: Verify + commit**

Run: `cd backend && uv run python -c "from hiresense.config import Settings; s=Settings(); print(s.analytics_cache_ttl_seconds, s.analytics_target_salary_top_k, s.analytics_target_salary_min_sample)"`
Expected: `300 50 5`

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(analytics): add analytics settings"
```

---

## Task 2: SalaryParser (pure, TDD)

**Files:** Create `backend/src/hiresense/analytics/domain/salary.py`; Test `backend/tests/unit/analytics/test_salary_parser.py`.

- [ ] **Step 1: Write the failing test**

```python
from hiresense.analytics.domain import SalaryParser


def test_parses_annual_range_usd():
    p = SalaryParser()
    r = p.parse("$100,000 - $120,000 per year")
    assert r is not None
    assert r.currency == "USD"
    assert r.min_annual == 100000
    assert r.max_annual == 120000


def test_parses_k_suffix_eur():
    r = SalaryParser().parse("€80k–€100k")
    assert r is not None
    assert r.currency == "EUR"
    assert r.min_annual == 80000
    assert r.max_annual == 100000


def test_parses_single_value_gbp():
    r = SalaryParser().parse("£90,000")
    assert r is not None and r.currency == "GBP"
    assert r.min_annual == 90000 and r.max_annual == 90000


def test_normalizes_hourly_to_annual():
    r = SalaryParser().parse("$50/hour")
    assert r is not None and r.currency == "USD"
    assert r.min_annual == 50 * 2080  # 104000


def test_normalizes_monthly_to_annual():
    r = SalaryParser().parse("$8,000/month")
    assert r is not None and r.min_annual == 8000 * 12


def test_unparseable_returns_none():
    p = SalaryParser()
    assert p.parse("competitive") is None
    assert p.parse("") is None
    assert p.parse(None) is None
```

- [ ] **Step 2: Run → FAIL**

Run: `cd backend && uv run python -m pytest tests/unit/analytics/test_salary_parser.py -v`
Expected: import error.

- [ ] **Step 3: Implement** `salary.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "eur": "EUR", "gbp": "GBP"}
_HOURS_PER_YEAR = 2080
_MONTHS_PER_YEAR = 12
# A number with optional thousands separators and an optional k suffix.
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kK])?"


@dataclass(frozen=True)
class ParsedSalary:
    currency: str
    min_annual: int
    max_annual: int


def _detect_currency(text: str) -> str | None:
    for token, code in _CURRENCY.items():
        if token in text.lower() if token.isalpha() else token in text:
            return code
    return None


def _to_number(value: str, k: str | None) -> float:
    n = float(value.replace(",", ""))
    if k:
        n *= 1000
    return n


def _period_multiplier(text: str) -> int:
    t = text.lower()
    if "hour" in t or "/hr" in t or "/h" in t:
        return _HOURS_PER_YEAR
    if "month" in t or "/mo" in t:
        return _MONTHS_PER_YEAR
    return 1


class SalaryParser:
    """Best-effort free-text salary parser. Returns None on unparseable input.

    Handles $/€/£ (+ usd/eur/gbp), comma thousands, `k` suffixes, single value
    or range, and hourly/monthly→annual normalization. Lossy by design.
    """

    def parse(self, raw: str | None) -> ParsedSalary | None:
        if not raw or not raw.strip():
            return None
        currency = _detect_currency(raw)
        if currency is None:
            return None
        numbers = [_to_number(v, k) for v, k in re.findall(_NUM, raw)]
        numbers = [n for n in numbers if n > 0]
        if not numbers:
            return None
        mult = _period_multiplier(raw)
        annual = sorted(int(round(n * mult)) for n in numbers)
        return ParsedSalary(currency=currency, min_annual=annual[0], max_annual=annual[-1])
```

- [ ] **Step 4: Run → PASS.** Then re-export in `analytics/domain/__init__.py` (create it):

```python
from hiresense.analytics.domain.salary import ParsedSalary, SalaryParser

__all__ = ["ParsedSalary", "SalaryParser"]
```

(This `__init__.py` will accumulate re-exports across the following tasks.)

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/salary.py backend/src/hiresense/analytics/domain/__init__.py backend/tests/unit/analytics/test_salary_parser.py
git commit -m "feat(analytics): add SalaryParser"
```

---

## Task 3: SkillNormalizer (pure, TDD)

**Files:** Create `backend/src/hiresense/analytics/domain/skill_normalizer.py`; Test `backend/tests/unit/analytics/test_skill_normalizer.py`.

- [ ] **Step 1: Write the failing test**

```python
from hiresense.analytics.domain import SkillNormalizer


def test_lowercases_and_trims():
    assert SkillNormalizer().normalize("  Python  ") == "python"


def test_applies_aliases():
    n = SkillNormalizer()
    assert n.normalize("React.js") == "react"
    assert n.normalize("ReactJS") == "react"
    assert n.normalize("k8s") == "kubernetes"
    assert n.normalize("JS") == "javascript"


def test_empty_is_empty():
    assert SkillNormalizer().normalize("   ") == ""
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `skill_normalizer.py`:

```python
from __future__ import annotations

_ALIASES = {
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "node.js": "node",
    "nodejs": "node",
    "postgres": "postgresql",
    "py": "python",
}


class SkillNormalizer:
    """Lowercase/trim + a small alias map so skill variants collapse."""

    def normalize(self, skill: str) -> str:
        base = (skill or "").strip().lower()
        return _ALIASES.get(base, base)
```

- [ ] **Step 4: Run → PASS.** Add to `analytics/domain/__init__.py`:

```python
from hiresense.analytics.domain.salary import ParsedSalary, SalaryParser
from hiresense.analytics.domain.skill_normalizer import SkillNormalizer

__all__ = ["ParsedSalary", "SalaryParser", "SkillNormalizer"]
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/skill_normalizer.py backend/src/hiresense/analytics/domain/__init__.py backend/tests/unit/analytics/test_skill_normalizer.py
git commit -m "feat(analytics): add SkillNormalizer"
```

---

## Task 4: TtlCache (pure, TDD)

**Files:** Create `backend/src/hiresense/analytics/domain/ttl_cache.py`; Test `backend/tests/unit/analytics/test_ttl_cache.py`.

- [ ] **Step 1: Write the failing test** (inject a clock so the test is deterministic — no real sleep):

```python
from hiresense.analytics.domain import TtlCache


def test_caches_within_ttl_and_recomputes_after():
    now = {"t": 1000.0}
    cache = TtlCache(ttl_seconds=5, clock=lambda: now["t"])
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return calls["n"]

    assert cache.get_or_compute("k", compute) == 1
    now["t"] = 1004.0
    assert cache.get_or_compute("k", compute) == 1  # within ttl → cached
    assert calls["n"] == 1
    now["t"] = 1006.0
    assert cache.get_or_compute("k", compute) == 2  # ttl expired → recompute
    assert calls["n"] == 2
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `ttl_cache.py`:

```python
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class TtlCache:
    """Tiny per-key time-based cache. `clock` is injectable for testing."""

    def __init__(self, *, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._store: dict[str, tuple[float, Any]] = {}

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        now = self._clock()
        hit = self._store.get(key)
        if hit is not None and (now - hit[0]) < self._ttl:
            return hit[1]
        value = compute()
        self._store[key] = (now, value)
        return value
```

- [ ] **Step 4: Run → PASS.** Add to `analytics/domain/__init__.py` (`from hiresense.analytics.domain.ttl_cache import TtlCache`, add `"TtlCache"` to `__all__`).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/ttl_cache.py backend/src/hiresense/analytics/domain/__init__.py backend/tests/unit/analytics/test_ttl_cache.py
git commit -m "feat(analytics): add TtlCache"
```

---

## Task 5: CorpusAnalyticsRepository

**Files:** Create `backend/src/hiresense/analytics/infrastructure/corpus_repository.py` + `__init__.py`; Test `backend/tests/integration/test_corpus_repository.py`.

This reads `ingested_jobs` for aggregation. It returns raw rows; the services do the normalization/parsing. Methods needed: open-job skill lists, remote_modality counts, weekly posting counts, salary_range strings, and salary strings for a set of job ids (for the target band).

- [ ] **Step 1: Write the failing integration test** (real SQLite; seed `IngestedJob` rows):

```python
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401
from hiresense.analytics.infrastructure import CorpusAnalyticsRepository


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(factory):
    with factory() as s:
        s.add_all([
            IngestedJob(id="1", bucket="boards", source="x", source_type="board",
                        title="A", skills=["Python", "React"], remote_modality="remote",
                        salary_range="$100k-$120k", status="open", identity_key="k1",
                        posted_date=datetime(2026, 5, 1, tzinfo=timezone.utc)),
            IngestedJob(id="2", bucket="boards", source="x", source_type="board",
                        title="B", skills=["python", "go"], remote_modality="on_site",
                        salary_range="competitive", status="open", identity_key="k2",
                        posted_date=datetime(2026, 5, 8, tzinfo=timezone.utc)),
            IngestedJob(id="3", bucket="boards", source="x", source_type="board",
                        title="C", skills=["rust"], remote_modality="remote",
                        salary_range=None, status="closed", identity_key="k3",
                        posted_date=datetime(2026, 5, 8, tzinfo=timezone.utc)),
        ])
        s.commit()


def test_open_skill_lists_excludes_closed():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    lists = repo.open_skill_lists()
    # 2 open jobs → 2 skill lists; the closed "rust" job is excluded.
    assert len(lists) == 2
    flat = sorted(s for sub in lists for s in sub)
    assert "Python" in flat and "rust" not in flat


def test_remote_modality_counts_open_only():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    counts = repo.remote_modality_counts()
    assert counts.get("remote") == 1 and counts.get("on_site") == 1


def test_open_salary_strings_and_total():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    salaries, total_open = repo.open_salary_strings()
    assert total_open == 2
    assert "$100k-$120k" in salaries and "competitive" in salaries


def test_salary_strings_for_ids():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    assert repo.salary_strings_for_ids(["1", "3"]) == {"1": "$100k-$120k", "3": None}
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `corpus_repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from hiresense.ingestion.infrastructure.models import IngestedJob


class CorpusAnalyticsRepository:
    """Read-only aggregation over the ingested-job corpus (status='open')."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def open_skill_lists(self) -> list[list[str]]:
        with self._session_factory() as session:
            stmt = select(IngestedJob.skills).where(IngestedJob.status == "open")
            return [list(row or []) for row in session.scalars(stmt).all()]

    def remote_modality_counts(self) -> dict[str, int]:
        with self._session_factory() as session:
            stmt = (
                select(IngestedJob.remote_modality, func.count())
                .where(IngestedJob.status == "open", IngestedJob.remote_modality.is_not(None))
                .group_by(IngestedJob.remote_modality)
            )
            return {row[0]: row[1] for row in session.execute(stmt).all()}

    def posting_dates(self) -> list[datetime]:
        with self._session_factory() as session:
            stmt = select(IngestedJob.posted_date).where(
                IngestedJob.status == "open", IngestedJob.posted_date.is_not(None)
            )
            return [d for d in session.scalars(stmt).all() if d is not None]

    def open_salary_strings(self) -> tuple[list[str], int]:
        with self._session_factory() as session:
            total = session.scalar(
                select(func.count()).select_from(IngestedJob).where(IngestedJob.status == "open")
            ) or 0
            stmt = select(IngestedJob.salary_range).where(
                IngestedJob.status == "open", IngestedJob.salary_range.is_not(None)
            )
            return [s for s in session.scalars(stmt).all() if s], int(total)

    def salary_strings_for_ids(self, job_ids: list[str]) -> dict[str, str | None]:
        if not job_ids:
            return {}
        with self._session_factory() as session:
            stmt = select(IngestedJob.id, IngestedJob.salary_range).where(
                IngestedJob.id.in_(job_ids)
            )
            return {row[0]: row[1] for row in session.execute(stmt).all()}
```

Create `analytics/infrastructure/__init__.py`:

```python
from hiresense.analytics.infrastructure.corpus_repository import CorpusAnalyticsRepository

__all__ = ["CorpusAnalyticsRepository"]
```

- [ ] **Step 4: Run → PASS** (note: `test_open_salary_strings_and_total` includes "competitive" because `open_salary_strings` returns all non-null salary strings; parsing happens later in `MarketIntelService`).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/infrastructure/ backend/tests/integration/test_corpus_repository.py
git commit -m "feat(analytics): add CorpusAnalyticsRepository"
```

---

## Task 6: FunnelService

**Files:** Create `backend/src/hiresense/analytics/domain/funnel_service.py`; Test `backend/tests/unit/analytics/test_funnel_service.py`.

Stages in order: `saved, applied, interviewing, offered, accepted`. `rejected` is a terminal outcome counted separately. "Reached stage N" = the app's history contains a row whose `to_status` is N **or any later stage** (monotonic high-water mark — an app now `rejected` that has an `interviewing` row counts as having reached interviewing). Conversion(N→N+1) = reached(N+1)/reached(N). Time-in-stage(N) = median over apps of `(first changed_at of the next stage) − (first changed_at of stage N)`, in days; only apps that left stage N contribute.

- [ ] **Step 1: Write the failing test**

```python
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from hiresense.analytics.domain import FunnelService
from hiresense.tracking.domain.status_transition import StatusTransition


class _FakeHistory:
    def __init__(self, rows):
        self._rows = rows

    def list_history(self):
        return self._rows

    def history_for(self, application_id):
        return [r for r in self._rows if r.application_id == application_id]


def _t(app, frm, to, day):
    return StatusTransition(
        application_id=app, from_status=frm, to_status=to,
        changed_at=datetime(2026, 5, day, tzinfo=timezone.utc),
    )


def test_reached_counts_and_conversion():
    a, b = uuid_mod.uuid4(), uuid_mod.uuid4()
    rows = [
        _t(a, None, "saved", 1), _t(a, "saved", "applied", 3), _t(a, "applied", "interviewing", 6),
        _t(b, None, "saved", 1), _t(b, "saved", "applied", 2), _t(b, "applied", "rejected", 5),
    ]
    m = FunnelService(_FakeHistory(rows)).compute()
    reached = {s.stage: s.reached for s in m.stages}
    assert reached["saved"] == 2
    assert reached["applied"] == 2
    assert reached["interviewing"] == 1   # only a (b went to rejected w/o interviewing)
    assert m.rejected == 1
    # conversion applied->interviewing = 1/2 = 0.5
    conv = {s.stage: s.conversion_from_prev for s in m.stages}
    assert conv["interviewing"] == 0.5


def test_time_in_stage_applied_median_days():
    a = uuid_mod.uuid4()
    rows = [_t(a, None, "saved", 1), _t(a, "saved", "applied", 3), _t(a, "applied", "interviewing", 8)]
    m = FunnelService(_FakeHistory(rows)).compute()
    times = {s.stage: s.median_days_in_stage for s in m.stages}
    # time in applied = day8 - day3 = 5 days
    assert times["applied"] == 5.0
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `funnel_service.py`:

```python
from __future__ import annotations

import statistics
import uuid as uuid_mod
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

_STAGES = ["saved", "applied", "interviewing", "offered", "accepted"]
_RANK = {s: i for i, s in enumerate(_STAGES)}


class FunnelStage(BaseModel):
    stage: str
    reached: int
    conversion_from_prev: float | None
    median_days_in_stage: float | None
    current: int


class FunnelMetrics(BaseModel):
    stages: list[FunnelStage]
    rejected: int
    total_applications: int


class FunnelService:
    def __init__(self, history: Any) -> None:
        self._history = history

    def compute(self) -> FunnelMetrics:
        rows = self._history.list_history()
        by_app: dict[uuid_mod.UUID, list] = defaultdict(list)
        for r in rows:
            by_app[r.application_id].append(r)

        reached = {s: 0 for s in _STAGES}
        current = {s: 0 for s in _STAGES}
        rejected = 0
        # first time each app entered each stage (by changed_at)
        first_entry: dict[str, list[float]] = defaultdict(list)  # stage -> [epoch days]

        for app_rows in by_app.values():
            app_rows = sorted(app_rows, key=lambda r: (r.changed_at, _RANK.get(r.to_status, 99)))
            to_statuses = [r.to_status for r in app_rows]
            # high-water mark across non-terminal stages
            max_rank = -1
            entered_at: dict[str, float] = {}
            for r in app_rows:
                if r.to_status in _RANK:
                    max_rank = max(max_rank, _RANK[r.to_status])
                    entered_at.setdefault(r.to_status, r.changed_at.timestamp() / 86400.0)
            for s in _STAGES:
                if max_rank >= _RANK[s]:
                    reached[s] += 1
            if "rejected" in to_statuses:
                rejected += 1
            # current status = the last row's to_status
            last = to_statuses[-1]
            if last in current:
                current[last] += 1
            for s, day in entered_at.items():
                first_entry[s].append(day)

        # time-in-stage: for apps that entered both stage N and N+1, the gap.
        stages_out: list[FunnelStage] = []
        for i, s in enumerate(_STAGES):
            conv: float | None = None
            if i > 0:
                prev = reached[_STAGES[i - 1]]
                conv = round(reached[s] / prev, 4) if prev else None
            # median time spent in stage s = median(entry[s+1] - entry[s]) over apps with both
            median_days: float | None = None
            if i + 1 < len(_STAGES):
                nxt = _STAGES[i + 1]
                gaps = []
                for app_rows in by_app.values():
                    entered: dict[str, float] = {}
                    for r in sorted(app_rows, key=lambda r: r.changed_at):
                        if r.to_status in _RANK:
                            entered.setdefault(r.to_status, r.changed_at.timestamp() / 86400.0)
                    if s in entered and nxt in entered:
                        gaps.append(entered[nxt] - entered[s])
                if gaps:
                    median_days = round(statistics.median(gaps), 2)
            stages_out.append(
                FunnelStage(
                    stage=s, reached=reached[s], conversion_from_prev=conv,
                    median_days_in_stage=median_days, current=current[s],
                )
            )
        return FunnelMetrics(stages=stages_out, rejected=rejected, total_applications=len(by_app))
```

- [ ] **Step 4: Run → PASS.** Add `FunnelService`, `FunnelMetrics`, `FunnelStage` to `analytics/domain/__init__.py` re-exports + `__all__`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/funnel_service.py backend/src/hiresense/analytics/domain/__init__.py backend/tests/unit/analytics/test_funnel_service.py
git commit -m "feat(analytics): add FunnelService"
```

---

## Task 7: MarketIntelService

**Files:** Create `backend/src/hiresense/analytics/domain/market_service.py`; Test `backend/tests/unit/analytics/test_market_service.py`.

Reads the corpus repo; uses `SkillNormalizer` + `SalaryParser`. Salary distribution groups by currency and reports the dominant currency's min/median/max + counts.

- [ ] **Step 1: Write the failing test** (fake corpus repo):

```python
from datetime import datetime, timezone

from hiresense.analytics.domain import MarketIntelService, SalaryParser, SkillNormalizer


class _FakeCorpus:
    def open_skill_lists(self):
        return [["Python", "React"], ["python", "Go"], ["PYTHON"]]

    def remote_modality_counts(self):
        return {"remote": 5, "on_site": 3, "hybrid": 2}

    def posting_dates(self):
        return [datetime(2026, 5, 1, tzinfo=timezone.utc), datetime(2026, 5, 2, tzinfo=timezone.utc),
                datetime(2026, 5, 9, tzinfo=timezone.utc)]

    def open_salary_strings(self):
        return (["$100k-$120k", "$90k", "competitive"], 4)

    def salary_strings_for_ids(self, ids):
        return {}


def _svc():
    return MarketIntelService(_FakeCorpus(), SkillNormalizer(), SalaryParser())


def test_top_skills_normalized_and_counted():
    intel = _svc().compute(top_skills=10)
    top = {s.skill: s.count for s in intel.top_skills}
    assert top["python"] == 3  # Python/python/PYTHON collapse
    assert top["react"] == 1


def test_remote_mix_passthrough():
    intel = _svc().compute(top_skills=10)
    assert intel.remote_mix["remote"] == 5


def test_salary_distribution_dominant_currency():
    intel = _svc().compute(top_skills=10)
    d = intel.salary_distribution
    assert d.currency == "USD"
    assert d.parsed_count == 2 and d.unparsed_count == 1
    assert d.min_annual == 90000 and d.max_annual == 120000


def test_weekly_trend_buckets():
    intel = _svc().compute(top_skills=10)
    # 3 postings across 2 ISO weeks
    assert sum(p.count for p in intel.posting_trend) == 3
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `market_service.py`:

```python
from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from pydantic import BaseModel


class SkillCount(BaseModel):
    skill: str
    count: int
    pct: float


class TrendPoint(BaseModel):
    week: str       # ISO year-week, e.g. "2026-W18"
    count: int


class SalaryDistribution(BaseModel):
    currency: str | None
    min_annual: int | None
    median_annual: int | None
    max_annual: int | None
    parsed_count: int
    unparsed_count: int
    other_currency_count: int


class MarketIntel(BaseModel):
    top_skills: list[SkillCount]
    remote_mix: dict[str, int]
    posting_trend: list[TrendPoint]
    salary_distribution: SalaryDistribution


class MarketIntelService:
    def __init__(self, corpus: Any, normalizer: Any, salary_parser: Any) -> None:
        self._corpus = corpus
        self._norm = normalizer
        self._salary = salary_parser

    def compute(self, *, top_skills: int = 20) -> MarketIntel:
        return MarketIntel(
            top_skills=self._top_skills(top_skills),
            remote_mix=self._corpus.remote_modality_counts(),
            posting_trend=self._trend(),
            salary_distribution=self._salary_distribution(),
        )

    def _top_skills(self, limit: int) -> list[SkillCount]:
        counter: Counter[str] = Counter()
        n_jobs = 0
        for skills in self._corpus.open_skill_lists():
            n_jobs += 1
            seen = {self._norm.normalize(s) for s in skills if s and s.strip()}
            seen.discard("")
            counter.update(seen)
        total = max(n_jobs, 1)
        return [
            SkillCount(skill=skill, count=count, pct=round(100.0 * count / total, 1))
            for skill, count in counter.most_common(limit)
        ]

    def _trend(self) -> list[TrendPoint]:
        weeks: Counter[str] = Counter()
        for d in self._corpus.posting_dates():
            iso = d.isocalendar()
            weeks[f"{iso[0]}-W{iso[1]:02d}"] += 1
        return [TrendPoint(week=w, count=c) for w, c in sorted(weeks.items())]

    def _salary_distribution(self) -> SalaryDistribution:
        strings, _total = self._corpus.open_salary_strings()
        by_currency: dict[str, list[int]] = {}
        unparsed = 0
        for s in strings:
            parsed = self._salary.parse(s)
            if parsed is None:
                unparsed += 1
                continue
            mid = (parsed.min_annual + parsed.max_annual) // 2
            by_currency.setdefault(parsed.currency, []).append(mid)
        if not by_currency:
            return SalaryDistribution(
                currency=None, min_annual=None, median_annual=None, max_annual=None,
                parsed_count=0, unparsed_count=unparsed, other_currency_count=0,
            )
        dominant = max(by_currency, key=lambda c: len(by_currency[c]))
        vals = sorted(by_currency[dominant])
        other = sum(len(v) for c, v in by_currency.items() if c != dominant)
        return SalaryDistribution(
            currency=dominant, min_annual=vals[0],
            median_annual=int(statistics.median(vals)), max_annual=vals[-1],
            parsed_count=len(vals), unparsed_count=unparsed, other_currency_count=other,
        )
```

- [ ] **Step 4: Run → PASS.** Add `MarketIntelService`, `MarketIntel`, `SkillCount`, `TrendPoint`, `SalaryDistribution` to `analytics/domain/__init__.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/market_service.py backend/src/hiresense/analytics/domain/__init__.py backend/tests/unit/analytics/test_market_service.py
git commit -m "feat(analytics): add MarketIntelService"
```

---

## Task 8: SkillGapService

**Files:** Create `backend/src/hiresense/analytics/domain/skill_gap_service.py`; Test `backend/tests/unit/analytics/test_skill_gap_service.py`.

Market skills (normalized) the profile lacks, ranked by corpus demand. Neutral state when no profile/skills.

- [ ] **Step 1: Write the failing test**

```python
from hiresense.analytics.domain import SkillGapService, SkillNormalizer


class _FakeCorpus:
    def open_skill_lists(self):
        return [["Python", "Kubernetes"], ["python", "k8s"], ["React", "Python"], ["Go"]]


def test_gap_excludes_profile_skills_and_ranks_by_demand():
    svc = SkillGapService(_FakeCorpus(), SkillNormalizer())
    gap = svc.compute(profile_skills=["Python"])
    skills = [g.skill for g in gap.missing]
    # python is in profile → excluded; kubernetes (2, via k8s alias) ranks above react (1)/go (1)
    assert "python" not in skills
    assert skills[0] == "kubernetes"
    top = gap.missing[0]
    assert top.count == 2 and top.pct == 50.0  # 2 of 4 open jobs


def test_no_profile_is_neutral():
    svc = SkillGapService(_FakeCorpus(), SkillNormalizer())
    gap = svc.compute(profile_skills=[])
    assert gap.has_profile is False
    assert gap.missing == []
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `skill_gap_service.py`:

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel


class SkillGapItem(BaseModel):
    skill: str
    count: int
    pct: float


class SkillGap(BaseModel):
    has_profile: bool
    missing: list[SkillGapItem]


class SkillGapService:
    def __init__(self, corpus: Any, normalizer: Any) -> None:
        self._corpus = corpus
        self._norm = normalizer

    def compute(self, *, profile_skills: list[str], limit: int = 20) -> SkillGap:
        if not profile_skills:
            return SkillGap(has_profile=False, missing=[])
        have = {self._norm.normalize(s) for s in profile_skills if s and s.strip()}
        have.discard("")
        counter: Counter[str] = Counter()
        n_jobs = 0
        for skills in self._corpus.open_skill_lists():
            n_jobs += 1
            seen = {self._norm.normalize(s) for s in skills if s and s.strip()}
            seen.discard("")
            counter.update(seen)
        total = max(n_jobs, 1)
        missing = [
            SkillGapItem(skill=skill, count=count, pct=round(100.0 * count / total, 1))
            for skill, count in counter.most_common()
            if skill not in have
        ][:limit]
        return SkillGap(has_profile=True, missing=missing)
```

- [ ] **Step 4: Run → PASS.** Add `SkillGapService`, `SkillGap`, `SkillGapItem` to `analytics/domain/__init__.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/skill_gap_service.py backend/src/hiresense/analytics/domain/__init__.py backend/tests/unit/analytics/test_skill_gap_service.py
git commit -m "feat(analytics): add SkillGapService"
```

---

## Task 9: TargetSalaryService

**Files:** Create `backend/src/hiresense/analytics/domain/target_salary_service.py`; Test `backend/tests/unit/analytics/test_target_salary_service.py`.

Embed the profile, search the vector store for similar jobs, parse their salaries, report median + p25–p75 over the dominant currency. Insufficient-data / no-vector-store → explicit state.

- [ ] **Step 1: Write the failing test** (fake embedding/vector store/corpus)

```python
import pytest

from hiresense.analytics.domain import SalaryParser, TargetSalaryService


class _Emb:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3]]


class _Scored:
    def __init__(self, id):
        self.id = id
        self.score = 0.9
        self.metadata = {}


class _Store:
    def __init__(self, ids):
        self._ids = ids

    async def search(self, query_embedding, *, top_k=10, filters=None):
        return [_Scored(i) for i in self._ids]


class _Corpus:
    def __init__(self, salaries):
        self._salaries = salaries

    def salary_strings_for_ids(self, ids):
        return self._salaries


def _svc(store, corpus):
    return TargetSalaryService(
        embedding=_Emb(), vector_store=store, corpus=corpus,
        salary_parser=SalaryParser(), top_k=50, min_sample=3,
    )


@pytest.mark.asyncio
async def test_band_from_similar_salaried_jobs():
    store = _Store(["1", "2", "3", "4"])
    corpus = _Corpus({"1": "$100k", "2": "$120k", "3": "$140k", "4": "competitive"})
    res = await _svc(store, corpus).compute(profile_skills=["python"], summary="backend")
    assert res.insufficient_data is False
    assert res.currency == "USD"
    assert res.sample_size == 3
    assert res.median_annual == 120000
    assert res.p25_annual <= res.median_annual <= res.p75_annual


@pytest.mark.asyncio
async def test_insufficient_sample():
    store = _Store(["1"])
    corpus = _Corpus({"1": "$100k"})
    res = await _svc(store, corpus).compute(profile_skills=["python"], summary="x")
    assert res.insufficient_data is True
    assert res.sample_size == 1


@pytest.mark.asyncio
async def test_no_vector_store():
    svc = TargetSalaryService(embedding=_Emb(), vector_store=None, corpus=_Corpus({}),
                              salary_parser=SalaryParser(), top_k=50, min_sample=3)
    res = await svc.compute(profile_skills=["python"], summary="x")
    assert res.insufficient_data is True


@pytest.mark.asyncio
async def test_no_profile():
    store = _Store(["1", "2", "3"])
    svc = _svc(store, _Corpus({"1": "$100k", "2": "$110k", "3": "$120k"}))
    res = await svc.compute(profile_skills=[], summary="")
    assert res.insufficient_data is True
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `target_salary_service.py`:

```python
from __future__ import annotations

import logging
import statistics
from collections import Counter
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TargetSalary(BaseModel):
    insufficient_data: bool
    currency: str | None = None
    p25_annual: int | None = None
    median_annual: int | None = None
    p75_annual: int | None = None
    sample_size: int = 0


def _percentile(sorted_vals: list[int], q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, max(0, round(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


class TargetSalaryService:
    def __init__(self, *, embedding: Any, vector_store: Any, corpus: Any,
                 salary_parser: Any, top_k: int, min_sample: int) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._corpus = corpus
        self._salary = salary_parser
        self._top_k = top_k
        self._min_sample = min_sample

    async def compute(self, *, profile_skills: list[str], summary: str) -> TargetSalary:
        text = f"{' '.join(profile_skills)}\n{summary}".strip()
        if self._vector_store is None or not text:
            return TargetSalary(insufficient_data=True)
        try:
            vectors = await self._embedding.embed([text])
            results = await self._vector_store.search(vectors[0], top_k=self._top_k)
        except Exception:
            logger.exception("target-salary: embedding/search failed")
            return TargetSalary(insufficient_data=True)
        ids = [r.id for r in results]
        salary_by_id = self._corpus.salary_strings_for_ids(ids)
        by_currency: dict[str, list[int]] = {}
        for raw in salary_by_id.values():
            parsed = self._salary.parse(raw)
            if parsed is None:
                continue
            mid = (parsed.min_annual + parsed.max_annual) // 2
            by_currency.setdefault(parsed.currency, []).append(mid)
        if not by_currency:
            return TargetSalary(insufficient_data=True)
        dominant = max(by_currency, key=lambda c: len(by_currency[c]))
        vals = sorted(by_currency[dominant])
        if len(vals) < self._min_sample:
            return TargetSalary(insufficient_data=True, currency=dominant, sample_size=len(vals))
        return TargetSalary(
            insufficient_data=False, currency=dominant,
            p25_annual=_percentile(vals, 0.25),
            median_annual=int(statistics.median(vals)),
            p75_annual=_percentile(vals, 0.75),
            sample_size=len(vals),
        )
```

- [ ] **Step 4: Run → PASS.** Add `TargetSalaryService`, `TargetSalary` to `analytics/domain/__init__.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/analytics/domain/target_salary_service.py backend/src/hiresense/analytics/domain/__init__.py backend/tests/unit/analytics/test_target_salary_service.py
git commit -m "feat(analytics): add TargetSalaryService"
```

---

## Task 10: AnalyticsService facade + schemas

**Files:** Create `backend/src/hiresense/analytics/domain/analytics_service.py`; `backend/src/hiresense/analytics/api/schemas.py`; update `analytics/domain/__init__.py` + create `analytics/__init__.py`.

`AnalyticsService` composes the four query services + TTL cache and is the single entry the API depends on.

- [ ] **Step 1: Implement `AnalyticsService`** (`analytics_service.py`):

```python
from __future__ import annotations

from typing import Any

from hiresense.analytics.domain.funnel_service import FunnelMetrics, FunnelService
from hiresense.analytics.domain.market_service import MarketIntel, MarketIntelService
from hiresense.analytics.domain.skill_gap_service import SkillGap, SkillGapService
from hiresense.analytics.domain.target_salary_service import TargetSalary, TargetSalaryService


class AnalyticsService:
    """Facade over the analytics query services. The API depends on this."""

    def __init__(
        self,
        *,
        funnel: FunnelService,
        market: MarketIntelService,
        skill_gap: SkillGapService,
        target_salary: TargetSalaryService,
        profile_service: Any,
        cache: Any,
        language: str = "en",
    ) -> None:
        self._funnel = funnel
        self._market = market
        self._skill_gap = skill_gap
        self._target_salary = target_salary
        self._profile = profile_service
        self._cache = cache
        self._language = language

    def funnel(self) -> FunnelMetrics:
        return self._funnel.compute()

    def market(self) -> MarketIntel:
        return self._cache.get_or_compute("market", self._market.compute)

    def skill_gap(self) -> SkillGap:
        return self._skill_gap.compute(profile_skills=self._profile_skills())

    async def target_salary(self) -> TargetSalary:
        view = self._profile.get_for_language(self._language)
        skills = list(view.skills) if view else []
        summary = view.summary if view else ""
        return await self._target_salary.compute(profile_skills=skills, summary=summary)

    def _profile_skills(self) -> list[str]:
        view = self._profile.get_for_language(self._language)
        return list(view.skills) if view else []
```

(NOTE: `market()` is cached; `target_salary` is async and reads the profile fresh — it is cached at the API layer in Task 12 via the same `TtlCache` keyed `"target_salary"` using an async-aware path; for simplicity here `target_salary` is computed each call and the cache wraps only the synchronous market result. The salary distribution is the dominant cost and is cached; the target band's vector search is acceptable per-call at single-user scale. This matches the spec's "cache the heavy results" intent without an async-cache complication.)

- [ ] **Step 2: Schemas** (`api/schemas.py`) — response models are the domain Pydantic models themselves (they're already `BaseModel`s). Re-export them for the routes:

```python
from __future__ import annotations

from hiresense.analytics.domain import (
    FunnelMetrics,
    MarketIntel,
    SkillGap,
    TargetSalary,
)

__all__ = ["FunnelMetrics", "MarketIntel", "SkillGap", "TargetSalary"]
```

- [ ] **Step 3: Re-exports** — add `AnalyticsService` to `analytics/domain/__init__.py`; create `analytics/__init__.py` (empty module marker or re-export the service):

```python
# backend/src/hiresense/analytics/__init__.py
from hiresense.analytics.domain import AnalyticsService

__all__ = ["AnalyticsService"]
```

- [ ] **Step 4: Verify import + commit**

Run: `cd backend && uv run python -c "from hiresense.analytics import AnalyticsService; print('ok')"`
Expected: `ok`.

```bash
git add backend/src/hiresense/analytics/domain/analytics_service.py backend/src/hiresense/analytics/domain/__init__.py backend/src/hiresense/analytics/__init__.py backend/src/hiresense/analytics/api/schemas.py
git commit -m "feat(analytics): add AnalyticsService facade + api schemas"
```

---

## Task 11: API layer (provider, dependencies, routes, __init__)

**Files:** Create `backend/src/hiresense/analytics/api/{provider.py,dependencies.py,routes.py,__init__.py}`.

- [ ] **Step 1: provider.py**

```python
from __future__ import annotations

from hiresense.analytics.domain import AnalyticsService


class AnalyticsProvider:
    def __init__(self, analytics_service: AnalyticsService) -> None:
        self._analytics_service = analytics_service

    def get_analytics_service(self) -> AnalyticsService:
        return self._analytics_service
```

- [ ] **Step 2: dependencies.py**

```python
from __future__ import annotations

from fastapi import Request

from hiresense.analytics.domain import AnalyticsService


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics.get_analytics_service()
```

- [ ] **Step 3: routes.py**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from hiresense.analytics.api.dependencies import get_analytics_service
from hiresense.analytics.domain import AnalyticsService, FunnelMetrics, MarketIntel, SkillGap, TargetSalary
from hiresense.identity.api.dependencies import require_auth

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_auth)])


@router.get("/funnel", response_model=FunnelMetrics)
def funnel(service: AnalyticsService = Depends(get_analytics_service)) -> FunnelMetrics:
    return service.funnel()


@router.get("/market", response_model=MarketIntel)
def market(service: AnalyticsService = Depends(get_analytics_service)) -> MarketIntel:
    return service.market()


@router.get("/skill-gap", response_model=SkillGap)
def skill_gap(service: AnalyticsService = Depends(get_analytics_service)) -> SkillGap:
    return service.skill_gap()


@router.get("/target-salary", response_model=TargetSalary)
async def target_salary(service: AnalyticsService = Depends(get_analytics_service)) -> TargetSalary:
    return await service.target_salary()
```

- [ ] **Step 4: __init__.py**

```python
from hiresense.analytics.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 5: Verify import + commit**

Run: `cd backend && uv run python -c "from hiresense.analytics.api import router; print(len(router.routes))"`
Expected: prints `4`.

```bash
git add backend/src/hiresense/analytics/api/
git commit -m "feat(analytics): add API provider, dependencies, routes"
```

---

## Task 12: Bootstrap + main wiring

**Files:** Create `backend/src/hiresense/bootstrap/analytics.py`; Modify `bootstrap/tracking.py`, `bootstrap/__init__.py`, `main.py`.

- [ ] **Step 1: Expose the history read repo from tracking** — in `bootstrap/tracking.py`, add `status_history_read` to `TrackingBuild` and return it:

```python
@dataclass(frozen=True)
class TrackingBuild:
    provider: TrackingProvider
    service: TrackingService
    status_history_read: Any


def build_tracking(infra: SharedInfra, ingestion_orchestrator: Any) -> TrackingBuild:
    tracking_repo = TrackingRepository(session_factory=infra.sync_session_factory)
    tracking_service = TrackingService(
        repository=tracking_repo,
        ingestion_orchestrator=ingestion_orchestrator,
        event_bus=infra.event_bus,
    )
    provider = TrackingProvider(tracking_service=tracking_service)
    return TrackingBuild(
        provider=provider, service=tracking_service, status_history_read=tracking_repo
    )
```

- [ ] **Step 2: build_analytics** (`bootstrap/analytics.py`):

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.analytics.api.provider import AnalyticsProvider
from hiresense.analytics.domain import (
    AnalyticsService,
    FunnelService,
    MarketIntelService,
    SalaryParser,
    SkillGapService,
    SkillNormalizer,
    TargetSalaryService,
    TtlCache,
)
from hiresense.analytics.infrastructure import CorpusAnalyticsRepository
from hiresense.bootstrap.shared_infra import SharedInfra


@dataclass(frozen=True)
class AnalyticsBuild:
    provider: AnalyticsProvider
    service: AnalyticsService


def build_analytics(infra: SharedInfra, profile_service: Any, status_history_read: Any) -> AnalyticsBuild:
    s = infra.settings
    corpus = CorpusAnalyticsRepository(session_factory=infra.sync_session_factory)
    normalizer = SkillNormalizer()
    salary_parser = SalaryParser()
    service = AnalyticsService(
        funnel=FunnelService(status_history_read),
        market=MarketIntelService(corpus, normalizer, salary_parser),
        skill_gap=SkillGapService(corpus, normalizer),
        target_salary=TargetSalaryService(
            embedding=infra.embedding,
            vector_store=infra.vector_store,
            corpus=corpus,
            salary_parser=salary_parser,
            top_k=s.analytics_target_salary_top_k,
            min_sample=s.analytics_target_salary_min_sample,
        ),
        profile_service=profile_service,
        cache=TtlCache(ttl_seconds=s.analytics_cache_ttl_seconds),
    )
    return AnalyticsBuild(provider=AnalyticsProvider(analytics_service=service), service=service)
```

- [ ] **Step 3: bootstrap/__init__.py** — add the imports + `__all__` entries (mirror existing entries):

```python
from hiresense.bootstrap.analytics import AnalyticsBuild, build_analytics
```
(add `"AnalyticsBuild"` and `"build_analytics"` to `__all__`.)

- [ ] **Step 4: main.py** — import the router and wire after tracking. Add near the other router imports:

```python
from hiresense.analytics.api import router as analytics_router
```
And in `create_app()`, after the tracking block:

```python
    # --- Analytics (read-only funnel + market + skill-gap) ---
    analytics = build_analytics(infra, profile.service, tracking.status_history_read)
    app.state.analytics = analytics.provider
    app.include_router(analytics_router)
```
Add `build_analytics` to the `from hiresense.bootstrap import (...)` list at the top of main.py.

- [ ] **Step 5: Verify the app builds**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/bootstrap/analytics.py backend/src/hiresense/bootstrap/tracking.py backend/src/hiresense/bootstrap/__init__.py backend/src/hiresense/main.py
git commit -m "feat(analytics): wire analytics context into the app"
```

---

## Task 13: Integration tests for the four endpoints

**Files:** Create `backend/tests/integration/test_analytics_endpoints.py`.

Mirror `tests/integration/test_preference_flow.py`: in-memory SQLite + `StaticPool`, override `require_auth`, mount the analytics router with a real `AnalyticsService` built over seeded data + fakes for embedding/vector store.

- [ ] **Step 1: Write the integration test**

```python
import uuid as uuid_mod
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.analytics.api import router as analytics_router
from hiresense.analytics.api.dependencies import get_analytics_service
from hiresense.analytics.domain import (
    AnalyticsService, FunnelService, MarketIntelService, SalaryParser,
    SkillGapService, SkillNormalizer, TargetSalaryService, TtlCache,
)
from hiresense.analytics.infrastructure import CorpusAnalyticsRepository
from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401
from hiresense.tracking.domain.models import TrackedApplication
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm  # noqa: F401
from hiresense.tracking.infrastructure.status_history_orm import ApplicationStatusHistoryOrm  # noqa: F401
from hiresense.tracking.infrastructure.repository import TrackingRepository


class _FakeProfile:
    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "backend engineer"})()


class _Emb:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3]]


class _Store:
    async def search(self, query_embedding, *, top_k=10, filters=None):
        return []  # no similar jobs in this fixture → target-salary insufficient


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(factory):
    with factory() as s:
        s.add(IngestedJob(id="1", bucket="boards", source="x", source_type="board", title="A",
                          skills=["Python", "React"], remote_modality="remote",
                          salary_range="$100k-$120k", status="open", identity_key="k1",
                          posted_date=datetime(2026, 5, 1, tzinfo=timezone.utc)))
        s.commit()
    repo = TrackingRepository(session_factory=factory)
    app = repo.create(TrackedApplication(title="A", company="Acme", status="saved"))
    app.status = "applied"
    repo.save_with_history(app, from_status="saved", to_status="applied")
    return repo


def _build_app(factory, history):
    corpus = CorpusAnalyticsRepository(session_factory=factory)
    norm, sal = SkillNormalizer(), SalaryParser()
    service = AnalyticsService(
        funnel=FunnelService(history),
        market=MarketIntelService(corpus, norm, sal),
        skill_gap=SkillGapService(corpus, norm),
        target_salary=TargetSalaryService(embedding=_Emb(), vector_store=_Store(), corpus=corpus,
                                          salary_parser=sal, top_k=50, min_sample=5),
        profile_service=_FakeProfile(),
        cache=TtlCache(ttl_seconds=300),
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_analytics_service] = lambda: service
    app.include_router(analytics_router)
    return app


@pytest.mark.asyncio
async def test_funnel_endpoint():
    factory = _factory(); history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/funnel")
        assert r.status_code == 200
        data = r.json()
        reached = {s["stage"]: s["reached"] for s in data["stages"]}
        assert reached["applied"] == 1 and reached["saved"] == 1
        assert data["total_applications"] == 1


@pytest.mark.asyncio
async def test_market_endpoint():
    factory = _factory(); history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/market")
        assert r.status_code == 200
        data = r.json()
        assert any(s["skill"] == "python" for s in data["top_skills"])
        assert data["salary_distribution"]["currency"] == "USD"


@pytest.mark.asyncio
async def test_skill_gap_endpoint():
    factory = _factory(); history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/skill-gap")
        assert r.status_code == 200
        data = r.json()
        assert data["has_profile"] is True
        # market has python+react; profile has python → react is a gap
        assert any(g["skill"] == "react" for g in data["missing"])


@pytest.mark.asyncio
async def test_target_salary_insufficient():
    factory = _factory(); history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/target-salary")
        assert r.status_code == 200
        assert r.json()["insufficient_data"] is True  # _Store returns no matches
```

- [ ] **Step 2: Run → PASS**

Run: `cd backend && uv run python -m pytest tests/integration/test_analytics_endpoints.py -v`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_analytics_endpoints.py
git commit -m "test(analytics): integration tests for the four endpoints"
```

---

## Task 14: Final verification

- [ ] **Step 1: Full suite**

Run: `cd backend && uv run python -m pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 2: Lint the analytics files this branch added**

Run: `cd backend && uv run python -m ruff check src/hiresense/analytics src/hiresense/bootstrap/analytics.py tests/unit/analytics tests/integration/test_analytics_endpoints.py tests/integration/test_corpus_repository.py`
Expected: clean (fix any issues with `--fix`). (Pre-existing repo-wide ruff debt is out of scope.)

- [ ] **Step 3: App composition smoke**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: `ok`.

---

## Self-Review notes

- **Spec coverage (§Architecture.2):** `SalaryParser` (T2) ✓; `SkillNormalizer` (T3) ✓; `TtlCache` (T4) ✓; `CorpusAnalyticsRepository` raw aggregation (T5) ✓; `FunnelService` reached/conversion/time-in-stage from the read port (T6) ✓; `MarketIntelService` top skills/remote mix/weekly trend/salary distribution by dominant currency (T7) ✓; `SkillGapService` normalized-literal demand-ranked gap + neutral state (T8) ✓; `TargetSalaryService` embedding→search→band + insufficient/no-vector-store states (T9) ✓; four auth-required GET endpoints (T11) ✓; bootstrap with the heavy results cached + tracking exposing the read port (T12) ✓; integration tests (T13) ✓.
- **Cache scope decision (documented in T10):** the TTL cache wraps the synchronous market result (the dominant salary-parse cost); the async target-salary band is computed per request (acceptable at single-user scale) — this avoids an async-cache complication while honoring "cache the heavy results". If target-salary cost becomes an issue, a later change can add an async-aware cached path keyed by profile signature.
- **Type/name consistency:** result models (`FunnelMetrics/FunnelStage`, `MarketIntel/SkillCount/TrendPoint/SalaryDistribution`, `SkillGap/SkillGapItem`, `TargetSalary`, `ParsedSalary`) defined once and re-exported via `analytics/domain/__init__.py`; `AnalyticsService` method names match the routes; `status_history_read` (the `TrackingRepository`) satisfies `FunnelService`'s `list_history()` use; `salary_strings_for_ids`/`open_salary_strings`/`open_skill_lists`/`remote_modality_counts`/`posting_dates` consistent between repo, services, and tests.
- **No placeholders:** every code step is complete; test fakes are concrete.
- **Out of scope:** the dashboard frontend (Phase 3 plan); seniority mix (not stored); persisted salary columns / rollups / cron.
