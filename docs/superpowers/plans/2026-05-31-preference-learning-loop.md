# Preference Learning Loop — Implementation Plan (Phase 1, backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a learning loop that re-ranks the job corpus toward the user's revealed taste — an explicit-feedback API drives a Rocchio "taste vector" that the existing pgvector ANN pre-ranking queries against, with full transparency and a reset.

**Architecture:** A new bounded context `preference` (`api → domain ← infrastructure`, ports as duck-typed `Any` per the existing `SemanticPreRanker` convention). It stores `FeedbackSignal`s (each snapshotting the signaled job's embedding) and a singleton `PreferenceModel` holding a decayed **feedback delta vector**. At retrieval time `SemanticPreRanker` asks `preference` to transform the baseline profile embedding into `taste = normalize(α·baseline + delta)`; with no model it returns the baseline unchanged, so today's behavior is the exact zero-signal default.

**Implementation refinement vs. the spec:** the spec described storing a precomputed `taste_vector` + `baseline_vector`. This plan instead stores only the decayed **delta** and blends it with the *live* baseline at query time. Same math (`taste = normalize(α·baseline + delta)`), but profile changes re-anchor automatically (the baseline is always fresh) and the stored model stays tiny. This strictly satisfies the spec's stated goals (re-anchor on profile change, resettable, decay).

**Scope:** Phase 1 = backend only (engine + persistence + API + retrieval integration). Phase 1 uses **explicit** feedback kinds only (`thumbs_up`, `thumbs_down`, `not_interested`, `more_like_this`). The Angular capture controls and Phase 2 (implicit tracking-outcome signals + dimension-weight nudging) are separate follow-up plans (see end).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy + Alembic, pgvector, pydantic, pydantic-settings, pytest. `uv run python -m pytest` to run tests (bare `uv run pytest` is broken on this machine).

---

## File Structure

**New — `preference` bounded context** (one class/enum per file, re-exported via `__init__.py` per the project's import-style rule):

- `backend/src/hiresense/preference/__init__.py`
- `backend/src/hiresense/preference/domain/__init__.py`
- `backend/src/hiresense/preference/domain/feedback_kind.py` — `FeedbackKind` enum (+ `.polarity`, `.weight_key`)
- `backend/src/hiresense/preference/domain/feedback_source.py` — `FeedbackSource` enum
- `backend/src/hiresense/preference/domain/feedback_signal.py` — `FeedbackSignal` model
- `backend/src/hiresense/preference/domain/preference_model.py` — `PreferenceModel` model
- `backend/src/hiresense/preference/domain/signal_contribution.py` — `SignalContribution` dataclass
- `backend/src/hiresense/preference/domain/taste_calculator.py` — `TasteVectorCalculator` (pure)
- `backend/src/hiresense/preference/domain/explanation.py` — `PreferenceExplanation` model + `build_explanation` function file *(two symbols → see note in Task 9)*
- `backend/src/hiresense/preference/domain/services.py` — `PreferenceService`
- `backend/src/hiresense/preference/ports/__init__.py`
- `backend/src/hiresense/preference/ports/repository.py` — `PreferenceRepositoryPort` Protocol
- `backend/src/hiresense/preference/infrastructure/__init__.py`
- `backend/src/hiresense/preference/infrastructure/orm.py` — `FeedbackSignalOrm`, `PreferenceModelOrm`
- `backend/src/hiresense/preference/infrastructure/repository.py` — `PreferenceRepository`
- `backend/src/hiresense/preference/api/__init__.py` — exports `router`
- `backend/src/hiresense/preference/api/schemas.py`
- `backend/src/hiresense/preference/api/routes.py`
- `backend/src/hiresense/preference/api/provider.py` — `PreferenceProvider`
- `backend/src/hiresense/preference/api/dependencies.py`
- `backend/src/hiresense/bootstrap/preference.py` — `build_preference`
- `backend/alembic/versions/016_create_preference_tables.py`

**Modified:**

- `backend/src/hiresense/config.py` — add preference settings
- `backend/.env.example` — document the new settings
- `backend/src/hiresense/ports/vector_store.py` — add `get_vector` to `VectorStorePort`
- `backend/src/hiresense/adapters/vector_store/pgvector_adapter.py` — implement `get_vector`
- `backend/src/hiresense/ingestion/domain/semantic_pre_ranker.py` — inject optional `preference`
- `backend/src/hiresense/bootstrap/ingestion.py` — thread `preference_query` into `SemanticPreRanker`
- `backend/src/hiresense/bootstrap/__init__.py` — export `build_preference`
- `backend/src/hiresense/main.py` — build preference, register router, wire into ingestion

**Tests:**

- `backend/tests/unit/preference/__init__.py`
- `backend/tests/unit/preference/test_feedback_kind.py`
- `backend/tests/unit/preference/test_taste_calculator.py`
- `backend/tests/unit/preference/test_preference_service.py`
- `backend/tests/unit/preference/test_explanation.py`
- `backend/tests/unit/ingestion/test_semantic_pre_ranker_preference.py`
- `backend/tests/integration/test_preference_flow.py`

---

## Task 1: Preference settings

**Files:**
- Modify: `backend/src/hiresense/config.py` (append fields to the `Settings` class, after the matching-weights block ~line 200)
- Modify: `backend/.env.example`

- [ ] **Step 1: Add settings fields**

In `backend/src/hiresense/config.py`, inside `class Settings(BaseSettings)`, after the `weight_interview: int = 10` line, add:

```python
    # --- Preference learning loop (taste vector via Rocchio relevance feedback) ---
    # Master switch: when False, query_vector() always returns the baseline.
    preference_enabled: bool = True
    # Blend coefficients: taste = normalize(alpha*baseline + beta*pos - gamma*neg)
    preference_alpha: float = 1.0
    preference_beta: float = 0.75
    preference_gamma: float = 0.5
    # Recency decay time constant in days (decay = exp(-age_days / tau)).
    preference_decay_tau_days: float = 90.0
    # Per-kind signal magnitudes (polarity is derived from the kind itself).
    preference_weight_thumbs_up: float = 1.0
    preference_weight_more_like_this: float = 1.0
    preference_weight_thumbs_down: float = 1.0
    preference_weight_not_interested: float = 1.5
```

- [ ] **Step 2: Document in `.env.example`**

Append to `backend/.env.example`:

```dotenv
# --- Preference learning loop ---
# Master switch for taste-vector re-ranking (true/false).
PREFERENCE_ENABLED=true
# Blend coefficients: taste = normalize(alpha*baseline + beta*positives - gamma*negatives)
PREFERENCE_ALPHA=1.0
PREFERENCE_BETA=0.75
PREFERENCE_GAMMA=0.5
# Recency decay time constant in days.
PREFERENCE_DECAY_TAU_DAYS=90.0
# Per-kind signal magnitudes.
PREFERENCE_WEIGHT_THUMBS_UP=1.0
PREFERENCE_WEIGHT_MORE_LIKE_THIS=1.0
PREFERENCE_WEIGHT_THUMBS_DOWN=1.0
PREFERENCE_WEIGHT_NOT_INTERESTED=1.5
```

- [ ] **Step 3: Verify config loads**

Run: `cd backend && uv run python -c "from hiresense.config import Settings; s=Settings(); print(s.preference_alpha, s.preference_weight_not_interested)"`
Expected: `1.0 1.5`

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(preference): add taste-vector learning settings"
```

---

## Task 2: `FeedbackKind` and `FeedbackSource` enums

**Files:**
- Create: `backend/src/hiresense/preference/__init__.py` (empty)
- Create: `backend/src/hiresense/preference/domain/__init__.py`
- Create: `backend/src/hiresense/preference/domain/feedback_source.py`
- Create: `backend/src/hiresense/preference/domain/feedback_kind.py`
- Create: `backend/tests/unit/preference/__init__.py` (empty)
- Test: `backend/tests/unit/preference/test_feedback_kind.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/preference/test_feedback_kind.py`:

```python
from hiresense.preference.domain import FeedbackKind, FeedbackSource


def test_explicit_kinds_exist() -> None:
    assert FeedbackKind.THUMBS_UP == "thumbs_up"
    assert FeedbackKind.THUMBS_DOWN == "thumbs_down"
    assert FeedbackKind.NOT_INTERESTED == "not_interested"
    assert FeedbackKind.MORE_LIKE_THIS == "more_like_this"


def test_polarity_is_plus_one_for_positive_kinds() -> None:
    assert FeedbackKind.THUMBS_UP.polarity == 1
    assert FeedbackKind.MORE_LIKE_THIS.polarity == 1


def test_polarity_is_minus_one_for_negative_kinds() -> None:
    assert FeedbackKind.THUMBS_DOWN.polarity == -1
    assert FeedbackKind.NOT_INTERESTED.polarity == -1


def test_weight_key_maps_to_settings_attribute() -> None:
    assert FeedbackKind.THUMBS_UP.weight_key == "preference_weight_thumbs_up"
    assert FeedbackKind.NOT_INTERESTED.weight_key == "preference_weight_not_interested"


def test_source_values() -> None:
    assert FeedbackSource.EXPLICIT == "explicit"
    assert FeedbackSource.IMPLICIT == "implicit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_feedback_kind.py -v`
Expected: FAIL — `ModuleNotFoundError: hiresense.preference`

- [ ] **Step 3: Create the package + enums**

Create `backend/src/hiresense/preference/__init__.py` (empty file).

Create `backend/src/hiresense/preference/domain/feedback_source.py`:

```python
from __future__ import annotations

import enum


class FeedbackSource(str, enum.Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
```

Create `backend/src/hiresense/preference/domain/feedback_kind.py`:

```python
from __future__ import annotations

import enum

_NEGATIVE = frozenset({"thumbs_down", "not_interested", "rejected"})


class FeedbackKind(str, enum.Enum):
    # Explicit (Phase 1)
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    NOT_INTERESTED = "not_interested"
    MORE_LIKE_THIS = "more_like_this"

    @property
    def polarity(self) -> int:
        """+1 pulls the taste vector toward the job, -1 pushes away."""
        return -1 if self.value in _NEGATIVE else 1

    @property
    def weight_key(self) -> str:
        """Name of the Settings attribute holding this kind's magnitude."""
        return f"preference_weight_{self.value}"
```

Create `backend/src/hiresense/preference/domain/__init__.py`:

```python
from hiresense.preference.domain.feedback_kind import FeedbackKind
from hiresense.preference.domain.feedback_source import FeedbackSource

__all__ = ["FeedbackKind", "FeedbackSource"]
```

Create empty `backend/tests/unit/preference/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_feedback_kind.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/__init__.py backend/src/hiresense/preference/domain backend/tests/unit/preference
git commit -m "feat(preference): add FeedbackKind and FeedbackSource enums"
```

---

## Task 3: Domain models — `FeedbackSignal`, `PreferenceModel`, `SignalContribution`

**Files:**
- Create: `backend/src/hiresense/preference/domain/feedback_signal.py`
- Create: `backend/src/hiresense/preference/domain/preference_model.py`
- Create: `backend/src/hiresense/preference/domain/signal_contribution.py`
- Modify: `backend/src/hiresense/preference/domain/__init__.py`
- Test: `backend/tests/unit/preference/test_feedback_kind.py` (append model tests)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/preference/test_feedback_kind.py`:

```python
import uuid
from datetime import datetime, timezone

from hiresense.preference.domain import (
    FeedbackSignal,
    PreferenceModel,
    SignalContribution,
)


def test_feedback_signal_defaults() -> None:
    sig = FeedbackSignal(
        job_id=uuid.uuid4(),
        kind=FeedbackKind.THUMBS_UP,
        source=FeedbackSource.EXPLICIT,
    )
    assert sig.id is None
    assert sig.job_embedding is None
    assert sig.created_at is None


def test_feedback_signal_holds_embedding() -> None:
    sig = FeedbackSignal(
        job_id=uuid.uuid4(),
        kind=FeedbackKind.NOT_INTERESTED,
        source=FeedbackSource.EXPLICIT,
        job_embedding=[0.1, 0.2, 0.3],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert sig.job_embedding == [0.1, 0.2, 0.3]


def test_preference_model_defaults() -> None:
    model = PreferenceModel(delta_vector=[0.0, 0.0])
    assert model.version == 1
    assert model.delta_vector == [0.0, 0.0]


def test_signal_contribution_fields() -> None:
    c = SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=2.0, age_days=10.0)
    assert c.polarity == 1
    assert c.age_days == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_feedback_kind.py -v`
Expected: FAIL — `ImportError: cannot import name 'FeedbackSignal'`

- [ ] **Step 3: Create the models**

Create `backend/src/hiresense/preference/domain/feedback_signal.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.preference.domain.feedback_kind import FeedbackKind
from hiresense.preference.domain.feedback_source import FeedbackSource


class FeedbackSignal(BaseModel):
    """A single piece of feedback about a job (pure domain model)."""

    id: uuid_mod.UUID | None = None
    job_id: uuid_mod.UUID
    kind: FeedbackKind
    source: FeedbackSource
    job_embedding: list[float] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
```

Create `backend/src/hiresense/preference/domain/preference_model.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PreferenceModel(BaseModel):
    """The learned preference state: a decayed feedback delta vector.

    The taste vector is reconstructed at query time as
    ``normalize(alpha*baseline + delta_vector)`` against the live profile
    baseline, so this model stays tiny and re-anchors automatically when the
    profile changes.
    """

    delta_vector: list[float]
    version: int = 1
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
```

Create `backend/src/hiresense/preference/domain/signal_contribution.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalContribution:
    """Resolved inputs for one signal's contribution to the delta vector."""

    embedding: list[float]
    polarity: int      # +1 or -1
    weight: float      # configured magnitude for the kind
    age_days: float    # signal age, for recency decay
```

Update `backend/src/hiresense/preference/domain/__init__.py`:

```python
from hiresense.preference.domain.feedback_kind import FeedbackKind
from hiresense.preference.domain.feedback_signal import FeedbackSignal
from hiresense.preference.domain.feedback_source import FeedbackSource
from hiresense.preference.domain.preference_model import PreferenceModel
from hiresense.preference.domain.signal_contribution import SignalContribution

__all__ = [
    "FeedbackKind",
    "FeedbackSignal",
    "FeedbackSource",
    "PreferenceModel",
    "SignalContribution",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_feedback_kind.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain
git commit -m "feat(preference): add FeedbackSignal, PreferenceModel, SignalContribution models"
```

---

## Task 4: `TasteVectorCalculator` (pure Rocchio math)

**Files:**
- Create: `backend/src/hiresense/preference/domain/taste_calculator.py`
- Modify: `backend/src/hiresense/preference/domain/__init__.py`
- Test: `backend/tests/unit/preference/test_taste_calculator.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/preference/test_taste_calculator.py`:

```python
import math

from hiresense.preference.domain import SignalContribution, TasteVectorCalculator


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def test_decay_is_one_at_zero_age() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    assert calc.decay(0.0) == 1.0


def test_decay_decreases_with_age() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    assert calc.decay(90.0) < calc.decay(10.0) < 1.0


def test_empty_contributions_give_zero_delta() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    assert calc.compute_delta([], dim=3) == [0.0, 0.0, 0.0]


def test_positive_signal_points_delta_toward_embedding() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    delta = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=1.0, age_days=0.0)],
        dim=2,
    )
    assert delta[0] > 0.0 and delta[1] == 0.0


def test_negative_signal_points_delta_away() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    delta = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=-1, weight=1.0, age_days=0.0)],
        dim=2,
    )
    assert delta[0] < 0.0


def test_older_signal_contributes_less_than_fresh() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    fresh = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=1.0, age_days=0.0)], dim=2
    )
    old = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=1.0, age_days=180.0)], dim=2
    )
    assert old[0] < fresh[0]


def test_blend_pulls_baseline_toward_delta_and_normalizes() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    taste = calc.blend([1.0, 0.0], [0.0, 1.0])
    assert math.isclose(_norm(taste), 1.0, rel_tol=1e-6)
    assert taste[1] > 0.0  # pulled toward the delta's axis


def test_blend_with_zero_delta_returns_normalized_baseline() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    taste = calc.blend([3.0, 4.0], [0.0, 0.0])
    assert math.isclose(taste[0], 0.6, rel_tol=1e-6)
    assert math.isclose(taste[1], 0.8, rel_tol=1e-6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_taste_calculator.py -v`
Expected: FAIL — `ImportError: cannot import name 'TasteVectorCalculator'`

- [ ] **Step 3: Implement the calculator**

Create `backend/src/hiresense/preference/domain/taste_calculator.py`:

```python
from __future__ import annotations

import math

from hiresense.preference.domain.signal_contribution import SignalContribution


class TasteVectorCalculator:
    """Pure Rocchio relevance-feedback math. No I/O — fully deterministic.

    delta = beta * Σ(decay·w·emb | positive) - gamma * Σ(decay·w·emb | negative)
    taste = normalize(alpha·baseline + delta)
    """

    def __init__(self, *, alpha: float, beta: float, gamma: float, tau_days: float) -> None:
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma
        self._tau_days = tau_days

    def decay(self, age_days: float) -> float:
        if self._tau_days <= 0:
            return 1.0
        return math.exp(-max(0.0, age_days) / self._tau_days)

    def compute_delta(self, contributions: list[SignalContribution], *, dim: int) -> list[float]:
        acc = [0.0] * dim
        for c in contributions:
            if len(c.embedding) != dim:
                continue
            coeff = self.decay(c.age_days) * c.weight
            coeff *= self._beta if c.polarity >= 0 else -self._gamma
            for i in range(dim):
                acc[i] += coeff * c.embedding[i]
        return acc

    def blend(self, baseline: list[float], delta: list[float]) -> list[float]:
        combined = [self._alpha * b + d for b, d in zip(baseline, delta)]
        return self._normalize(combined)

    @staticmethod
    def _normalize(v: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0.0:
            return v
        return [x / norm for x in v]
```

Add to `backend/src/hiresense/preference/domain/__init__.py` imports + `__all__`:

```python
from hiresense.preference.domain.taste_calculator import TasteVectorCalculator
```
(and add `"TasteVectorCalculator"` to `__all__`)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_taste_calculator.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain
git commit -m "feat(preference): add TasteVectorCalculator (Rocchio + decay)"
```

---

## Task 5: `get_vector` on the vector store port + pgvector adapter

**Files:**
- Modify: `backend/src/hiresense/ports/vector_store.py`
- Modify: `backend/src/hiresense/adapters/vector_store/pgvector_adapter.py`
- Test: `backend/tests/unit/preference/test_taste_calculator.py` is unrelated — add a focused parse test at `backend/tests/unit/preference/test_vector_parse.py`

- [ ] **Step 1: Write the failing test (vector literal parsing)**

Create `backend/tests/unit/preference/test_vector_parse.py`:

```python
from hiresense.adapters.vector_store.pgvector_adapter import _parse_vector


def test_parse_bracketed_vector() -> None:
    assert _parse_vector("[0.1,0.2,0.3]") == [0.1, 0.2, 0.3]


def test_parse_handles_spaces() -> None:
    assert _parse_vector("[1, 2, 3]") == [1.0, 2.0, 3.0]


def test_parse_empty_returns_empty() -> None:
    assert _parse_vector("[]") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_vector_parse.py -v`
Expected: FAIL — `ImportError: cannot import name '_parse_vector'`

- [ ] **Step 3: Add `get_vector` to the port**

In `backend/src/hiresense/ports/vector_store.py`, add to the `VectorStorePort` Protocol (after `search`):

```python
    async def get_vector(self, id: str) -> list[float] | None: ...
```

- [ ] **Step 4: Implement parsing + `get_vector` on the adapter**

In `backend/src/hiresense/adapters/vector_store/pgvector_adapter.py`, after `_vector_literal`:

```python
def _parse_vector(raw: str) -> list[float]:
    """Parse pgvector's text form '[0.1,0.2,...]' into floats."""
    inner = raw.strip().strip("[]").strip()
    if not inner:
        return []
    return [float(part) for part in inner.split(",")]
```

Add this method to the `PgVectorStore` class (after `search`):

```python
    async def get_vector(self, id: str) -> list[float] | None:
        stmt = text(f"SELECT embedding FROM {self._table} WHERE id = :id")
        with self._session_factory() as session:
            row = session.execute(stmt, {"id": id}).first()
        if row is None or row.embedding is None:
            return None
        return _parse_vector(str(row.embedding))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_vector_parse.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ports/vector_store.py backend/src/hiresense/adapters/vector_store/pgvector_adapter.py backend/tests/unit/preference/test_vector_parse.py
git commit -m "feat(vector-store): add get_vector(id) for embedding snapshots"
```

---

## Task 6: Repository port + ORM + repository

**Files:**
- Create: `backend/src/hiresense/preference/ports/__init__.py`
- Create: `backend/src/hiresense/preference/ports/repository.py`
- Create: `backend/src/hiresense/preference/infrastructure/__init__.py`
- Create: `backend/src/hiresense/preference/infrastructure/orm.py`
- Create: `backend/src/hiresense/preference/infrastructure/repository.py`

*(No unit test here — the repository is exercised by the DB-backed integration test in Task 12, mirroring how `TrackingRepository` is tested. The service unit tests in Task 8 use an in-memory fake repository.)*

- [ ] **Step 1: Define the repository port**

Create `backend/src/hiresense/preference/ports/repository.py`:

```python
from __future__ import annotations

from typing import Protocol

from hiresense.preference.domain import FeedbackSignal, PreferenceModel


class PreferenceRepositoryPort(Protocol):
    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal: ...

    def list_signals(self) -> list[FeedbackSignal]: ...

    def get_model(self) -> PreferenceModel | None: ...

    def save_model(self, model: PreferenceModel) -> PreferenceModel: ...

    def clear(self) -> None: ...
```

Create `backend/src/hiresense/preference/ports/__init__.py`:

```python
from hiresense.preference.ports.repository import PreferenceRepositoryPort

__all__ = ["PreferenceRepositoryPort"]
```

- [ ] **Step 2: Define the ORM**

Create `backend/src/hiresense/preference/infrastructure/orm.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base

# Embeddings are stored as JSON float arrays (not a pgvector column): the taste
# math runs in Python and the ANN query targets the separate vector_embeddings
# table, so no pgvector type is needed here. This keeps the tables portable to
# the sqlite-backed unit/integration harness, matching the project's choice to
# keep the `vector` type off ORM models.


class FeedbackSignalOrm(Base):
    __tablename__ = "feedback_signals"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    job_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    job_embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PreferenceModelOrm(Base):
    __tablename__ = "preference_models"

    # Singleton: one row, fixed id. (Multi-profile is a future extension.)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    delta_vector: Mapped[list] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 3: Implement the repository**

Create `backend/src/hiresense/preference/infrastructure/repository.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from hiresense.preference.domain import FeedbackSignal, PreferenceModel
from hiresense.preference.infrastructure.orm import FeedbackSignalOrm, PreferenceModelOrm

_MODEL_ID = 1


class PreferenceRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal:
        with self._session_factory() as session:
            row = FeedbackSignalOrm(
                job_id=signal.job_id,
                kind=signal.kind.value,
                source=signal.source.value,
                job_embedding=signal.job_embedding,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return FeedbackSignal.model_validate(row)

    def list_signals(self) -> list[FeedbackSignal]:
        with self._session_factory() as session:
            rows = session.scalars(select(FeedbackSignalOrm)).all()
            return [FeedbackSignal.model_validate(r) for r in rows]

    def get_model(self) -> PreferenceModel | None:
        with self._session_factory() as session:
            row = session.get(PreferenceModelOrm, _MODEL_ID)
            return PreferenceModel.model_validate(row) if row is not None else None

    def save_model(self, model: PreferenceModel) -> PreferenceModel:
        with self._session_factory() as session:
            row = session.get(PreferenceModelOrm, _MODEL_ID)
            if row is None:
                row = PreferenceModelOrm(id=_MODEL_ID, delta_vector=model.delta_vector, version=model.version)
                session.add(row)
            else:
                row.delta_vector = model.delta_vector
                row.version = model.version
            session.commit()
            session.refresh(row)
            return PreferenceModel.model_validate(row)

    def clear(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(FeedbackSignalOrm))
            session.execute(delete(PreferenceModelOrm))
            session.commit()
```

Create `backend/src/hiresense/preference/infrastructure/__init__.py`:

```python
from hiresense.preference.infrastructure.repository import PreferenceRepository

__all__ = ["PreferenceRepository"]
```

- [ ] **Step 4: Verify imports resolve**

Run: `cd backend && uv run python -c "from hiresense.preference.infrastructure import PreferenceRepository; from hiresense.preference.ports import PreferenceRepositoryPort; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/ports backend/src/hiresense/preference/infrastructure
git commit -m "feat(preference): add repository port, ORM, and repository"
```

---

## Task 7: Alembic migration `016`

**Files:**
- Create: `backend/alembic/versions/016_create_preference_tables.py`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/016_create_preference_tables.py`:

```python
"""create preference tables (feedback_signals, preference_models)

Backs the preference learning loop. Embeddings are stored as JSON float arrays
(the ANN query targets the separate vector_embeddings table; taste math is in
Python), so no pgvector column type is used here.

Revision ID: 016
Revises: 015
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_signals (
            id UUID PRIMARY KEY,
            job_id UUID NOT NULL,
            kind VARCHAR(32) NOT NULL,
            source VARCHAR(16) NOT NULL,
            job_embedding JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_signals_job_id ON feedback_signals (job_id)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS preference_models (
            id INTEGER PRIMARY KEY,
            delta_vector JSONB NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS preference_models")
    op.execute("DROP INDEX IF EXISTS ix_feedback_signals_job_id")
    op.execute("DROP TABLE IF EXISTS feedback_signals")
```

- [ ] **Step 2: Verify the migration script imports cleanly**

Run: `cd backend && uv run python -c "import importlib.util, pathlib; p=pathlib.Path('alembic/versions/016_create_preference_tables.py'); spec=importlib.util.spec_from_file_location('m016', p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(m.revision, m.down_revision)"`
Expected: `016 015`

*(The migration is applied against a real Postgres in the Task 12 integration run / `uv run python -m alembic upgrade head`.)*

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/016_create_preference_tables.py
git commit -m "feat(preference): migration for feedback_signals and preference_models"
```

---

## Task 8: `PreferenceService`

**Files:**
- Create: `backend/src/hiresense/preference/domain/services.py`
- Modify: `backend/src/hiresense/preference/domain/__init__.py`
- Test: `backend/tests/unit/preference/test_preference_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/preference/test_preference_service.py`:

```python
import uuid
from datetime import datetime, timezone

import pytest

from hiresense.preference.domain import (
    FeedbackKind,
    FeedbackSignal,
    PreferenceModel,
    TasteVectorCalculator,
)
from hiresense.preference.domain.services import PreferenceService


class FakeRepo:
    def __init__(self) -> None:
        self.signals: list[FeedbackSignal] = []
        self.model: PreferenceModel | None = None
        self.cleared = False

    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal:
        signal = signal.model_copy(update={"id": uuid.uuid4(), "created_at": datetime.now(timezone.utc)})
        self.signals.append(signal)
        return signal

    def list_signals(self) -> list[FeedbackSignal]:
        return list(self.signals)

    def get_model(self) -> PreferenceModel | None:
        return self.model

    def save_model(self, model: PreferenceModel) -> PreferenceModel:
        self.model = model
        return model

    def clear(self) -> None:
        self.signals.clear()
        self.model = None
        self.cleared = True


class FakeVectorStore:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    async def get_vector(self, id: str) -> list[float] | None:
        return self._vectors.get(id)


def _service(repo, vectors, *, weights=None) -> PreferenceService:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    return PreferenceService(
        repository=repo,
        vector_store=FakeVectorStore(vectors),
        calculator=calc,
        weights=weights or {k: 1.0 for k in FeedbackKind},
        enabled=True,
    )


@pytest.mark.asyncio
async def test_query_vector_returns_baseline_when_no_model() -> None:
    svc = _service(FakeRepo(), {})
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]


@pytest.mark.asyncio
async def test_record_signal_snapshots_embedding_and_builds_model() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    assert repo.signals[0].job_embedding == [0.0, 1.0]
    assert repo.model is not None
    # taste = normalize(baseline + delta); delta points along [0,1]
    taste = svc.query_vector([1.0, 0.0])
    assert taste[1] > 0.0


@pytest.mark.asyncio
async def test_negative_signal_pushes_query_vector_away() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.NOT_INTERESTED)
    taste = svc.query_vector([0.0, 1.0])
    assert taste[1] < 1.0  # pushed away from the disliked direction


@pytest.mark.asyncio
async def test_record_signal_without_embedding_still_stores_signal() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {})  # vector store has no embedding for this job
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    assert repo.signals[0].job_embedding is None
    # No contributing embeddings → delta is empty → query returns baseline
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]


@pytest.mark.asyncio
async def test_disabled_service_returns_baseline() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    svc._enabled = False  # noqa: SLF001 — exercise the master switch
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]


@pytest.mark.asyncio
async def test_reset_clears_signals_and_model() -> None:
    repo = FakeRepo()
    jid = uuid.uuid4()
    svc = _service(repo, {str(jid): [0.0, 1.0]})
    await svc.record_signal(jid, FeedbackKind.THUMBS_UP)
    svc.reset()
    assert repo.cleared is True
    assert svc.query_vector([1.0, 0.0]) == [1.0, 0.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_preference_service.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` for `PreferenceService`

- [ ] **Step 3: Implement the service**

Create `backend/src/hiresense/preference/domain/services.py`:

```python
from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from hiresense.preference.domain.feedback_kind import FeedbackKind
from hiresense.preference.domain.feedback_signal import FeedbackSignal
from hiresense.preference.domain.feedback_source import FeedbackSource
from hiresense.preference.domain.preference_model import PreferenceModel
from hiresense.preference.domain.signal_contribution import SignalContribution
from hiresense.preference.domain.taste_calculator import TasteVectorCalculator

logger = logging.getLogger(__name__)


class PreferenceService:
    def __init__(
        self,
        *,
        repository: Any,
        vector_store: Any,
        calculator: TasteVectorCalculator,
        weights: dict[FeedbackKind, float],
        enabled: bool,
    ) -> None:
        self._repo = repository
        self._vector_store = vector_store
        self._calc = calculator
        self._weights = weights
        self._enabled = enabled

    async def record_signal(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind
    ) -> FeedbackSignal:
        embedding: list[float] | None = None
        if self._vector_store is not None:
            try:
                embedding = await self._vector_store.get_vector(str(job_id))
            except Exception:
                logger.exception("preference: get_vector failed for %s", job_id)
        if embedding is None:
            logger.warning("preference: no embedding for job %s — signal stored, no contribution", job_id)
        signal = self._repo.add_signal(
            FeedbackSignal(
                job_id=job_id,
                kind=kind,
                source=FeedbackSource.EXPLICIT,
                job_embedding=embedding,
            )
        )
        self._recompute()
        return signal

    def query_vector(self, baseline: list[float]) -> list[float]:
        if not self._enabled:
            return baseline
        model = self._repo.get_model()
        if model is None or not model.delta_vector:
            return baseline
        if len(model.delta_vector) != len(baseline):
            return baseline
        return self._calc.blend(baseline, model.delta_vector)

    def list_signals(self) -> list[FeedbackSignal]:
        return self._repo.list_signals()

    def reset(self) -> None:
        self._repo.clear()

    def _recompute(self) -> None:
        signals = [s for s in self._repo.list_signals() if s.job_embedding]
        if not signals:
            return
        dim = len(signals[0].job_embedding)
        now = datetime.now(timezone.utc)
        contributions = [self._to_contribution(s, now) for s in signals]
        delta = self._calc.compute_delta(contributions, dim=dim)
        self._repo.save_model(PreferenceModel(delta_vector=delta))

    def _to_contribution(self, signal: FeedbackSignal, now: datetime) -> SignalContribution:
        created = signal.created_at or now
        age_days = max(0.0, (now - created).total_seconds() / 86400.0)
        return SignalContribution(
            embedding=signal.job_embedding or [],
            polarity=signal.kind.polarity,
            weight=self._weights.get(signal.kind, 1.0),
            age_days=age_days,
        )
```

Add to `backend/src/hiresense/preference/domain/__init__.py`:

```python
from hiresense.preference.domain.services import PreferenceService
```
(and add `"PreferenceService"` to `__all__`)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_preference_service.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain
git commit -m "feat(preference): add PreferenceService (record, query, reset)"
```

---

## Task 9: Explanation builder (transparency)

**Files:**
- Create: `backend/src/hiresense/preference/domain/explanation.py` *(contains the `PreferenceExplanation` model and the `build_explanation` function — these two symbols form one cohesive unit; grouping the function with the value object it returns is the closest fit to the one-symbol-per-file rule without an artificial split.)*
- Modify: `backend/src/hiresense/preference/domain/__init__.py`
- Modify: `backend/src/hiresense/preference/domain/services.py` (add `explain()`)
- Test: `backend/tests/unit/preference/test_explanation.py`

The Phase 1 explanation is **deterministic** (no LLM): signal counts by kind, positive/negative totals, the delta-vector magnitude, and whether the model is active. LLM phrasing ("toward remote-first backend…") is a deliberate Phase 2 enhancement — flagged in the spec as the fuzziest piece.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/preference/test_explanation.py`:

```python
import uuid

from hiresense.preference.domain import FeedbackKind, FeedbackSignal, FeedbackSource
from hiresense.preference.domain.explanation import build_explanation


def _sig(kind: FeedbackKind, emb=None) -> FeedbackSignal:
    return FeedbackSignal(
        id=uuid.uuid4(), job_id=uuid.uuid4(), kind=kind,
        source=FeedbackSource.EXPLICIT, job_embedding=emb,
    )


def test_empty_signals_report_inactive() -> None:
    exp = build_explanation([], delta_vector=None)
    assert exp.active is False
    assert exp.total_signals == 0
    assert exp.drift_magnitude == 0.0


def test_counts_by_kind_and_polarity() -> None:
    signals = [
        _sig(FeedbackKind.THUMBS_UP),
        _sig(FeedbackKind.THUMBS_UP),
        _sig(FeedbackKind.NOT_INTERESTED),
    ]
    exp = build_explanation(signals, delta_vector=[0.0, 0.0])
    assert exp.total_signals == 3
    assert exp.positive_count == 2
    assert exp.negative_count == 1
    assert exp.counts_by_kind["thumbs_up"] == 2


def test_drift_magnitude_is_delta_norm() -> None:
    exp = build_explanation([_sig(FeedbackKind.THUMBS_UP)], delta_vector=[3.0, 4.0])
    assert exp.active is True
    assert abs(exp.drift_magnitude - 5.0) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_explanation.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_explanation'`

- [ ] **Step 3: Implement the explanation**

Create `backend/src/hiresense/preference/domain/explanation.py`:

```python
from __future__ import annotations

import math
from collections import Counter

from pydantic import BaseModel

from hiresense.preference.domain.feedback_signal import FeedbackSignal


class PreferenceExplanation(BaseModel):
    active: bool
    total_signals: int
    positive_count: int
    negative_count: int
    counts_by_kind: dict[str, int]
    drift_magnitude: float


def build_explanation(
    signals: list[FeedbackSignal], *, delta_vector: list[float] | None
) -> PreferenceExplanation:
    counts = Counter(s.kind.value for s in signals)
    positive = sum(1 for s in signals if s.kind.polarity > 0)
    negative = sum(1 for s in signals if s.kind.polarity < 0)
    magnitude = (
        math.sqrt(sum(x * x for x in delta_vector)) if delta_vector else 0.0
    )
    return PreferenceExplanation(
        active=bool(delta_vector) and magnitude > 0.0,
        total_signals=len(signals),
        positive_count=positive,
        negative_count=negative,
        counts_by_kind=dict(counts),
        drift_magnitude=magnitude,
    )
```

Add `explain()` to `PreferenceService` in `services.py` (import at top: `from hiresense.preference.domain.explanation import PreferenceExplanation, build_explanation`):

```python
    def explain(self) -> PreferenceExplanation:
        model = self._repo.get_model()
        delta = model.delta_vector if model is not None else None
        return build_explanation(self._repo.list_signals(), delta_vector=delta)
```

Add to `backend/src/hiresense/preference/domain/__init__.py`:

```python
from hiresense.preference.domain.explanation import PreferenceExplanation, build_explanation
```
(add `"PreferenceExplanation"` and `"build_explanation"` to `__all__`)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_explanation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain
git commit -m "feat(preference): add deterministic explanation builder"
```

---

## Task 10: API layer — schemas, routes, provider, dependencies

**Files:**
- Create: `backend/src/hiresense/preference/api/schemas.py`
- Create: `backend/src/hiresense/preference/api/provider.py`
- Create: `backend/src/hiresense/preference/api/dependencies.py`
- Create: `backend/src/hiresense/preference/api/routes.py`
- Create: `backend/src/hiresense/preference/api/__init__.py`

- [ ] **Step 1: Schemas**

Create `backend/src/hiresense/preference/api/schemas.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.preference.domain import FeedbackKind


class FeedbackRequest(BaseModel):
    job_id: uuid_mod.UUID
    kind: FeedbackKind


class FeedbackSignalResponse(BaseModel):
    id: uuid_mod.UUID | None = None
    job_id: uuid_mod.UUID
    kind: FeedbackKind
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Provider + dependencies (mirror tracking)**

Create `backend/src/hiresense/preference/api/provider.py`:

```python
from __future__ import annotations

from hiresense.preference.domain import PreferenceService


class PreferenceProvider:
    def __init__(self, preference_service: PreferenceService) -> None:
        self._preference_service = preference_service

    def get_preference_service(self) -> PreferenceService:
        return self._preference_service
```

Create `backend/src/hiresense/preference/api/dependencies.py`:

```python
from __future__ import annotations

from fastapi import Request

from hiresense.preference.domain import PreferenceService


def get_preference_service(request: Request) -> PreferenceService:
    return request.app.state.preference.get_preference_service()
```

- [ ] **Step 3: Routes**

Create `backend/src/hiresense/preference/api/routes.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from hiresense.identity.api.dependencies import require_auth
from hiresense.preference.api.dependencies import get_preference_service
from hiresense.preference.api.schemas import FeedbackRequest, FeedbackSignalResponse
from hiresense.preference.domain import PreferenceService
from hiresense.preference.domain.explanation import PreferenceExplanation

router = APIRouter(prefix="/preference", tags=["preference"], dependencies=[Depends(require_auth)])


@router.post("/feedback", response_model=FeedbackSignalResponse, status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    service: PreferenceService = Depends(get_preference_service),
) -> FeedbackSignalResponse:
    signal = await service.record_signal(request.job_id, request.kind)
    return FeedbackSignalResponse.model_validate(signal)


@router.get("/signals", response_model=list[FeedbackSignalResponse])
def list_signals(
    service: PreferenceService = Depends(get_preference_service),
) -> list[FeedbackSignalResponse]:
    return [FeedbackSignalResponse.model_validate(s) for s in service.list_signals()]


@router.get("/explain", response_model=PreferenceExplanation)
def explain(
    service: PreferenceService = Depends(get_preference_service),
) -> PreferenceExplanation:
    return service.explain()


@router.post("/reset", status_code=204)
def reset(
    service: PreferenceService = Depends(get_preference_service),
) -> Response:
    service.reset()
    return Response(status_code=204)
```

Create `backend/src/hiresense/preference/api/__init__.py`:

```python
from hiresense.preference.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 4: Verify imports resolve**

Run: `cd backend && uv run python -c "from hiresense.preference.api import router; print(len(router.routes))"`
Expected: `4`

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/api
git commit -m "feat(preference): add API (feedback, signals, explain, reset)"
```

---

## Task 11: Bootstrap wiring + retrieval integration

**Files:**
- Create: `backend/src/hiresense/bootstrap/preference.py`
- Modify: `backend/src/hiresense/bootstrap/__init__.py`
- Modify: `backend/src/hiresense/ingestion/domain/semantic_pre_ranker.py`
- Modify: `backend/src/hiresense/bootstrap/ingestion.py`
- Modify: `backend/src/hiresense/main.py`
- Test: `backend/tests/unit/ingestion/test_semantic_pre_ranker_preference.py`

- [ ] **Step 1: Write the failing pre-ranker integration test**

Create `backend/tests/unit/ingestion/test_semantic_pre_ranker_preference.py`:

```python
from __future__ import annotations

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ports.vector_store import ScoredResult


def _job(id: str) -> NormalizedJob:
    return NormalizedJob(
        id=id, title=f"Job {id}", company="Co", description="d", skills=["python"],
        source="t", source_type="api", language="en", url=f"https://e/{id}",
    )


class FakeVectorStore:
    def __init__(self) -> None:
        self.last_query: list[float] | None = None

    async def search(self, query_embedding, *, top_k=10, filters=None):
        self.last_query = query_embedding
        return [ScoredResult(id="a", score=0.9, metadata={})]

    async def upsert(self, id, embedding, metadata): ...
    async def delete(self, ids): ...
    async def get_vector(self, id): return None


class FakeEmbedding:
    async def embed(self, texts): return [[1.0, 0.0]]


class FakePreference:
    """Transforms the baseline into a fixed taste vector."""

    def query_vector(self, baseline: list[float]) -> list[float]:
        return [0.0, 1.0]


@pytest.mark.asyncio
async def test_preference_transforms_query_vector() -> None:
    store = FakeVectorStore()
    ranker = SemanticPreRanker(
        store, FakeEmbedding(), top_k_cap=10, skill_weight=0.4, semantic_weight=0.6,
        preference=FakePreference(),
    )
    await ranker.rerank([_job("a")], {"a": None}, ["python"], "summary", "boards")
    assert store.last_query == [0.0, 1.0]  # taste vector, not the raw [1.0, 0.0]


@pytest.mark.asyncio
async def test_no_preference_uses_raw_profile_vector() -> None:
    store = FakeVectorStore()
    ranker = SemanticPreRanker(
        store, FakeEmbedding(), top_k_cap=10, skill_weight=0.4, semantic_weight=0.6,
    )
    await ranker.rerank([_job("a")], {"a": None}, ["python"], "summary", "boards")
    assert store.last_query == [1.0, 0.0]  # unchanged — backward compatible
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_semantic_pre_ranker_preference.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'preference'`

- [ ] **Step 3: Inject `preference` into `SemanticPreRanker`**

In `backend/src/hiresense/ingestion/domain/semantic_pre_ranker.py`, add a `preference` parameter to `__init__` (after `semantic_weight`):

```python
        semantic_weight: float,
        preference: Any = None,
    ) -> None:
```

and store it: `self._preference = preference` (alongside the other assignments).

In `rerank`, immediately after the line `profile_vec = await self._get_profile_embedding(candidate_skills, candidate_summary)` and its `None` guard, insert:

```python
        # Apply the learned taste vector (preference loop). Passthrough when no
        # preference port is wired or no model exists — baseline is returned.
        if self._preference is not None:
            try:
                profile_vec = self._preference.query_vector(profile_vec)
            except Exception:
                logger.exception("SemanticPreRanker: preference.query_vector failed — using baseline")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_semantic_pre_ranker_preference.py -v`
Expected: PASS (2 passed). Also run the existing suite: `uv run python -m pytest tests/unit/ingestion/test_semantic_pre_ranker.py -v` → still PASS.

- [ ] **Step 5: Create the preference builder**

Create `backend/src/hiresense/bootstrap/preference.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.preference.api.provider import PreferenceProvider
from hiresense.preference.domain import (
    FeedbackKind,
    PreferenceService,
    TasteVectorCalculator,
)
from hiresense.preference.infrastructure import PreferenceRepository


@dataclass(frozen=True)
class PreferenceBuild:
    provider: PreferenceProvider
    service: PreferenceService


def build_preference(infra: SharedInfra) -> PreferenceBuild:
    s = infra.settings
    calculator = TasteVectorCalculator(
        alpha=s.preference_alpha,
        beta=s.preference_beta,
        gamma=s.preference_gamma,
        tau_days=s.preference_decay_tau_days,
    )
    weights = {kind: float(getattr(s, kind.weight_key)) for kind in FeedbackKind}
    service = PreferenceService(
        repository=PreferenceRepository(session_factory=infra.sync_session_factory),
        vector_store=infra.vector_store,
        calculator=calculator,
        weights=weights,
        enabled=s.preference_enabled,
    )
    return PreferenceBuild(provider=PreferenceProvider(preference_service=service), service=service)
```

- [ ] **Step 6: Thread preference into `build_ingestion`**

In `backend/src/hiresense/bootstrap/ingestion.py`:
- Add a parameter to the `build_ingestion` function signature: `preference_query: Any = None` (ensure `from typing import Any` is imported — it is used elsewhere in the file).
- At the `SemanticPreRanker(` construction (around line 204), add the keyword argument `preference=preference_query,`.

- [ ] **Step 7: Export the builder + wire `main.py`**

In `backend/src/hiresense/bootstrap/__init__.py`, add:
```python
from hiresense.bootstrap.preference import PreferenceBuild, build_preference
```
and add `"PreferenceBuild"` and `"build_preference"` to `__all__`.

In `backend/src/hiresense/main.py`:
- Add to the bootstrap import block: `build_preference,`
- Add `from hiresense.preference.api import router as preference_router`
- **Before** the `# --- Ingestion` block, build preference:
```python
    # --- Preference (taste-vector learning; consumed by ingestion pre-ranking) ---
    preference = build_preference(infra)
    app.state.preference = preference.provider
    app.include_router(preference_router)
```
- Change the ingestion build line to pass the query service:
```python
    ingestion = build_ingestion(infra, tracked, preference_query=preference.service)
```

- [ ] **Step 8: Verify the app composes**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; app=create_app(); paths=[r.path for r in app.routes]; print([p for p in paths if 'preference' in p])"`
Expected: a list containing `/preference/feedback`, `/preference/signals`, `/preference/explain`, `/preference/reset`.

*(`PreferenceService` satisfies the duck-typed `preference` port: `SemanticPreRanker` only calls `.query_vector(baseline)`.)*

- [ ] **Step 9: Commit**

```bash
git add backend/src/hiresense/bootstrap backend/src/hiresense/main.py backend/src/hiresense/ingestion/domain/semantic_pre_ranker.py backend/tests/unit/ingestion/test_semantic_pre_ranker_preference.py
git commit -m "feat(preference): wire taste vector into ANN pre-ranking"
```

---

## Task 12: DB-backed integration test (end-to-end loop)

**Files:**
- Create: `backend/tests/integration/test_preference_flow.py`

This mirrors `backend/tests/integration/test_ingestion_to_api_flow.py` (real Postgres + `alembic upgrade head`). Inspect that file first to reuse its DB fixture/setup exactly; the test below assumes a `client` (httpx/TestClient against `create_app()`) and an authenticated request helper consistent with that existing test. Adapt fixture names to match.

- [ ] **Step 1: Write the integration test**

Create `backend/tests/integration/test_preference_flow.py`:

```python
"""End-to-end: feedback changes the taste vector, reset restores baseline.

Mirrors test_ingestion_to_api_flow.py for DB/app/auth setup — reuse the same
fixtures (real Postgres, migrations applied, authenticated client).
"""
from __future__ import annotations

import uuid

import pytest


@pytest.mark.integration
def test_feedback_builds_then_reset_clears_model(auth_client, seed_indexed_job) -> None:
    # seed_indexed_job: inserts a job row AND its embedding into vector_embeddings,
    # returning the job_id (str). Build it from the existing ingestion seed helper.
    job_id = seed_indexed_job(embedding=[0.0] * 768)

    # No signals yet → explain reports inactive.
    r = auth_client.get("/preference/explain")
    assert r.status_code == 200
    assert r.json()["active"] is False

    # Submit a thumbs-up → 201, signal stored.
    r = auth_client.post("/preference/feedback", json={"job_id": job_id, "kind": "thumbs_up"})
    assert r.status_code == 201

    # Signals list now has one entry.
    r = auth_client.get("/preference/signals")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # explain now reports the model active with one positive signal.
    body = auth_client.get("/preference/explain").json()
    assert body["active"] is True
    assert body["positive_count"] == 1

    # Reset → 204, then explain reports inactive and signals empty.
    assert auth_client.post("/preference/reset").status_code == 204
    assert auth_client.get("/preference/signals").json() == []
    assert auth_client.get("/preference/explain").json()["active"] is False
```

*(Note on the all-zero embedding: a zero vector yields a zero delta, so `active` would stay False. Use a non-zero embedding, e.g. `[1.0] + [0.0]*767`, so the delta is non-trivial. Adjust the seed value accordingly when wiring the fixture.)*

- [ ] **Step 2: Apply migrations and run**

Run:
```bash
cd backend && uv run python -m alembic upgrade head && uv run python -m pytest tests/integration/test_preference_flow.py -v
```
Expected: PASS. If the integration suite is gated (marker/env), run it the same way `test_ingestion_to_api_flow.py` is run in this repo.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_preference_flow.py
git commit -m "test(preference): DB-backed feedback→model→reset flow"
```

---

## Task 13: Full suite + lint

- [ ] **Step 1: Run the whole backend test suite**

Run: `cd backend && uv run python -m pytest -q`
Expected: all pass (no regressions in ingestion/matching).

- [ ] **Step 2: Lint**

Run: `cd backend && uv run ruff check src/hiresense/preference src/hiresense/ingestion/domain/semantic_pre_ranker.py`
Expected: no errors (fix any reported).

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A
git commit -m "chore(preference): lint clean-up"
```

---

## Follow-up plans (out of scope here)

- **Frontend capture controls** — thumbs / not-interested / more-like-this on Angular match cards calling `POST /preference/feedback`, plus a small "why is this ranked here?" surface reading `GET /preference/explain` and a reset button. Needs Angular-structure exploration; its own plan.
- **Phase 2 — implicit signals** — add a `tracking` status-change domain event, subscribe in `preference`, auto-emit implicit `FeedbackSignal`s (`applied`/`interviewing`/`offered`/`accepted`/`rejected`) with their own configured weights; add a nightly decay-consolidation job.
- **Phase 2 — dimension-weight nudging** — correlate dimension scores with positive outcomes, apply clamped, gated `weight_overrides` in the matching composite.
- **Explanation v2** — LLM-phrased drift summary ("toward remote-first backend, away from large-enterprise") layered over the deterministic counts.
```
