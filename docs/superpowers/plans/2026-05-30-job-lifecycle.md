# Job Lifecycle (Change + Closure Detection) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On refetch, recognize jobs we already have (updating them in place) and detect jobs that are no longer open (marking them `closed`, dropping them from search), instead of skipping/duplicating and letting dead listings linger.

**Architecture:** Centralize lifecycle on `JobsRepository` via an identity-keyed `upsert` (Approach A); both fetch loops (`IngestionOrchestrator`, `PortalScanner`) share it. Phase 1 adds the schema, upsert/change-detection, inline disappearance-based closure for snapshot sources, index removal, and the closed-job API/UI — all without new network calls. Phase 2 adds a throttled, scheduled URL-probe sweep with closed-content markers for feed/search sources.

**Tech Stack:** Python 3.13, SQLAlchemy + Alembic (Postgres / pgvector; sqlite for unit tests), FastAPI, pydantic, pytest; Angular frontend. Python is run with `uv` (`uv run python -m pytest`, `uv run python -m alembic` — bare `uv run pytest`/`alembic` are broken on this machine).

**Spec:** `docs/superpowers/specs/2026-05-30-job-lifecycle-design.md`

---

## File Structure

**Phase 1**
- `backend/src/hiresense/ingestion/domain/content_hash.py` — *Create.* Pure mutable-field hash.
- `backend/src/hiresense/ingestion/domain/closure_detector.py` — *Create.* Pure "which stored jobs to close" decision.
- `backend/src/hiresense/ingestion/domain/upsert_result.py` — *Create.* `UpsertResult` enum.
- `backend/src/hiresense/ingestion/domain/models.py` — *Modify.* Add `source_id`, `status` to `NormalizedJob`.
- `backend/src/hiresense/ingestion/infrastructure/models.py` — *Modify.* New ORM columns.
- `backend/alembic/versions/015_add_job_lifecycle_columns.py` — *Create.* Migration.
- `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py` — *Modify.* `upsert`, closure methods, `_to_orm`/`_to_domain`.
- `backend/src/hiresense/ingestion/infrastructure/in_memory_jobs_repository.py` — *Modify.* Mirror upsert + closure.
- `backend/src/hiresense/ingestion/ports/jobs_repository.py` — *Modify.* Port surface.
- `backend/src/hiresense/ingestion/ports/job_source.py` — *Modify.* Add `supports_snapshot_closure`.
- `backend/src/hiresense/ingestion/domain/job_embedding_indexer.py` — *Modify.* Add `remove`.
- `backend/src/hiresense/ingestion/domain/services.py` — *Modify.* Use upsert, reindex updated, run disappearance.
- `backend/src/hiresense/ingestion/domain/portal_scanner.py` — *Modify.* Same.
- `backend/src/hiresense/ingestion/adapters/{greenhouse_adapter,lever_adapter,ashby_adapter}.py` — *Modify.* `supports_snapshot_closure() -> True`.
- `backend/src/hiresense/ingestion/domain/job_filter.py` — *Modify.* `include_closed`.
- `backend/src/hiresense/ingestion/api/routes.py` — *Modify.* Thread `include_closed`; expose `status`.
- `frontend/src/app/pages/ingestion/ingestion.component.{ts,html,scss}` — *Modify.* Badge + toggle.

**Phase 2**
- `backend/src/hiresense/ingestion/domain/closed_listing_classifier.py` — *Create.* Pure `(status, body) -> verdict`.
- `backend/src/hiresense/ingestion/domain/job_revalidation_service.py` — *Create.* Throttled sweep.
- `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py` — *Modify.* `find_open_stale`.
- `backend/src/hiresense/config.py` + `backend/.env.example` — *Modify.* Phase 2 knobs.
- `backend/src/hiresense/bootstrap/ingestion.py` — *Modify.* Wire the service + trigger.
- `backend/src/hiresense/ingestion/api/routes.py` — *Modify.* Manual revalidation trigger endpoint.

---

# PHASE 1 — Inline lifecycle (no new network)

## Task 1: `content_hash` pure helper

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/content_hash.py`
- Modify: `backend/src/hiresense/ingestion/domain/__init__.py` (re-export)
- Test: `backend/tests/unit/ingestion/test_content_hash.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/ingestion/test_content_hash.py
from __future__ import annotations

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.content_hash import content_hash


def _job(**over) -> NormalizedJob:
    base = dict(
        id="x", title="Engineer", company="Acme", description="Build things",
        location="Remote", salary_range="$100k", skills=["python", "sql"],
        source="remotive", source_type="api", url="https://e.com/1",
    )
    base.update(over)
    return NormalizedJob(**base)


def test_same_content_same_hash() -> None:
    assert content_hash(_job()) == content_hash(_job())


def test_skill_order_does_not_change_hash() -> None:
    assert content_hash(_job(skills=["python", "sql"])) == content_hash(
        _job(skills=["sql", "python"])
    )


def test_changed_field_changes_hash() -> None:
    assert content_hash(_job()) != content_hash(_job(salary_range="$120k"))


def test_id_and_scores_do_not_affect_hash() -> None:
    assert content_hash(_job(id="a", match_score=0.9)) == content_hash(
        _job(id="b", match_score=0.1)
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_content_hash.py -v`
Expected: FAIL — `ModuleNotFoundError: ... content_hash`.

- [ ] **Step 3: Implement**

```python
# backend/src/hiresense/ingestion/domain/content_hash.py
from __future__ import annotations

import hashlib

from hiresense.ingestion.domain.models import NormalizedJob


def content_hash(job: NormalizedJob) -> str:
    """sha256 over the mutable fields that define 'has this posting changed?'.

    Excludes id, scores, and timestamps. Skills are sorted so reordering does
    not register as a change.
    """
    parts = [
        job.title.strip(),
        job.company.strip(),
        job.description.strip(),
        job.location.strip(),
        (job.salary_range or "").strip(),
        "|".join(sorted(s.strip().lower() for s in job.skills)),
    ]
    raw = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
```

Add to `backend/src/hiresense/ingestion/domain/__init__.py`:

```python
from hiresense.ingestion.domain.content_hash import content_hash
```
and add `"content_hash"` to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_content_hash.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/content_hash.py backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/ingestion/test_content_hash.py
git commit -m "feat(ingestion): add content_hash helper for change detection"
```

---

## Task 2: Domain model fields (`source_id`, `status`)

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/models.py:16-38` (`NormalizedJob`)
- Test: `backend/tests/unit/ingestion/test_models.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/unit/ingestion/test_models.py
from hiresense.ingestion.domain.models import NormalizedJob


def test_normalized_job_lifecycle_field_defaults() -> None:
    job = NormalizedJob(
        id="1", title="T", company="C", description="D",
        source="remotive", source_type="api", url="https://e.com/1",
    )
    assert job.source_id is None
    assert job.status == "open"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_models.py::test_normalized_job_lifecycle_field_defaults -v`
Expected: FAIL — `AttributeError`/validation: no `source_id`/`status`.

- [ ] **Step 3: Implement**

In `backend/src/hiresense/ingestion/domain/models.py`, add to `NormalizedJob` (after `id: str`):

```python
    source_id: str | None = None
    status: str = "open"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/models.py backend/tests/unit/ingestion/test_models.py
git commit -m "feat(ingestion): add source_id and status to NormalizedJob"
```

---

## Task 3: ORM columns

**Files:**
- Modify: `backend/src/hiresense/ingestion/infrastructure/models.py`

(No standalone unit test — exercised by the repository tests in Task 5/6 and the migration in Task 4. This step only changes the SQLAlchemy mapping so sqlite test tables include the columns.)

> **⚠ Keep the build green:** unit tests build tables from this ORM, and the
> repository (`_to_orm`/`add_if_absent`) still uses `dedup_key` until Task 5.
> So THIS task must (a) ADD the new columns in an insert-safe way (every new
> column nullable or defaulted, so the *unchanged* old repo can still insert),
> (b) KEEP `dedup_key` and its existing `UniqueConstraint`, and (c) NOT add the
> new `(bucket, source, identity_key)` unique constraint yet — `identity_key`
> is empty-default for now and would collide. Task 5 finalizes: it makes
> `identity_key` authoritative in `_to_orm`, swaps the constraint, and drops
> `dedup_key` — all together with the repo switch, in one green commit.

- [ ] **Step 1: Add columns to `IngestedJob`**

In `backend/src/hiresense/ingestion/infrastructure/models.py`, ADD a new index and the new columns. **Leave the existing `dedup_key` column and `UniqueConstraint("bucket","dedup_key", name="ux_ingested_jobs_bucket_dedup")` untouched.** All new columns are nullable or defaulted so existing inserts keep working:

```python
    __table_args__ = (
        UniqueConstraint("bucket", "dedup_key", name="ux_ingested_jobs_bucket_dedup"),  # unchanged; removed in Task 5
        Index("ix_ingested_jobs_bucket_fetched_at", "bucket", "fetched_at"),
        Index("ix_ingested_jobs_source", "source"),
        Index("ix_ingested_jobs_bucket_status_checked", "bucket", "status", "last_checked_at"),
    )
    # ... existing columns (incl. dedup_key) stay ...
    identity_key: Mapped[str | None] = mapped_column(String(64), nullable=True)  # tightened to NOT NULL in Task 5
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open", server_default="open")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    missed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
```

Add `Integer` to the `from sqlalchemy import ...` line. Do NOT remove `dedup_key`.

- [ ] **Step 2: Verify it imports AND the existing repo suite still passes**

Run: `cd backend && uv run python -c "from hiresense.ingestion.infrastructure.models import IngestedJob; print(sorted(IngestedJob.__table__.columns.keys()))"`
Expected: list includes the 9 new columns AND still includes `dedup_key`.

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_jobs_repository.py -v`
Expected: PASS — the old `add_if_absent`/`dedup_key` path is untouched and the new columns are insert-safe.

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/ingestion/infrastructure/models.py
git commit -m "feat(ingestion): add lifecycle columns to ingested_jobs ORM"
```

---

## Task 4: Alembic migration 015

**Files:**
- Create: `backend/alembic/versions/015_add_job_lifecycle_columns.py`

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/015_add_job_lifecycle_columns.py
"""add job lifecycle columns to ingested_jobs

Replaces the content-derived dedup_key with a stable identity_key
(source_id or sha256(url)) and adds change/closure-tracking columns.

Revision ID: 015
Revises: 014
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ingested_jobs", sa.Column("identity_key", sa.String(length=64), nullable=True))
    op.add_column("ingested_jobs", sa.Column("source_id", sa.String(length=255), nullable=True))
    op.add_column("ingested_jobs", sa.Column("status", sa.String(length=10), nullable=False, server_default="open"))
    op.add_column("ingested_jobs", sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("ingested_jobs", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingested_jobs", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingested_jobs", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingested_jobs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingested_jobs", sa.Column("missed_count", sa.Integer(), nullable=False, server_default="0"))

    # Backfill: identity_key = sha256(url) for every existing row (source_id is
    # unavailable historically); last_seen_at = fetched_at.
    op.execute("UPDATE ingested_jobs SET identity_key = encode(digest(url, 'sha256'), 'hex') WHERE identity_key IS NULL")
    op.execute("UPDATE ingested_jobs SET last_seen_at = fetched_at WHERE last_seen_at IS NULL")

    op.alter_column("ingested_jobs", "identity_key", nullable=False)
    op.alter_column("ingested_jobs", "last_seen_at", nullable=False, server_default=sa.text("now()"))

    op.drop_constraint("ux_ingested_jobs_bucket_dedup", "ingested_jobs", type_="unique")
    op.drop_column("ingested_jobs", "dedup_key")

    op.create_unique_constraint(
        "ux_ingested_jobs_bucket_source_identity", "ingested_jobs",
        ["bucket", "source", "identity_key"],
    )
    op.create_index(
        "ix_ingested_jobs_bucket_status_checked", "ingested_jobs",
        ["bucket", "status", "last_checked_at"],
    )

    op.alter_column("ingested_jobs", "status", server_default=None)
    op.alter_column("ingested_jobs", "content_hash", server_default=None)
    op.alter_column("ingested_jobs", "missed_count", server_default=None)


def downgrade() -> None:
    op.add_column("ingested_jobs", sa.Column("dedup_key", sa.String(length=64), nullable=True))
    op.execute("UPDATE ingested_jobs SET dedup_key = identity_key WHERE dedup_key IS NULL")
    op.alter_column("ingested_jobs", "dedup_key", nullable=False)
    op.drop_index("ix_ingested_jobs_bucket_status_checked", "ingested_jobs")
    op.drop_constraint("ux_ingested_jobs_bucket_source_identity", "ingested_jobs", type_="unique")
    op.create_unique_constraint("ux_ingested_jobs_bucket_dedup", "ingested_jobs", ["bucket", "dedup_key"])
    for col in ("missed_count", "updated_at", "closed_at", "last_checked_at", "last_seen_at", "content_hash", "status", "source_id", "identity_key"):
        op.drop_column("ingested_jobs", col)
```

> Note: `digest()` requires the `pgcrypto` extension. If not already enabled, add `op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")` as the first line of `upgrade()`.

- [ ] **Step 2: Run the migration against a scratch DB**

Run: `cd backend && uv run python -m alembic upgrade head`
Expected: `Running upgrade 014 -> 015`. Then `uv run python -m alembic downgrade -1` then `uv run python -m alembic upgrade head` to confirm reversibility.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/015_add_job_lifecycle_columns.py
git commit -m "feat(ingestion): migration for job lifecycle columns"
```

---

## Task 5: `UpsertResult` + DB repository `upsert`

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/upsert_result.py`
- Modify: `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py`
- Test: `backend/tests/unit/ingestion/test_jobs_repository.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/unit/ingestion/test_jobs_repository.py
from hiresense.ingestion.domain.upsert_result import UpsertResult


def _job(repo_id: str, **over):
    from hiresense.ingestion.domain.models import NormalizedJob
    base = dict(
        id=repo_id, title="Engineer", company="Acme", description="D",
        source="remotive", source_type="api", url="https://e.com/1",
        source_id="native-1",
    )
    base.update(over)
    return NormalizedJob(**base)


def test_upsert_inserts_then_unchanged(repo):  # `repo` = existing fixture/sync repo
    assert repo.upsert(_job("a")) == UpsertResult.INSERTED
    assert repo.upsert(_job("b")) == UpsertResult.UNCHANGED  # same identity+content


def test_upsert_updates_changed_fields_and_preserves_id(repo):
    repo.upsert(_job("a"))
    assert repo.upsert(_job("b", salary_range="$200k")) == UpsertResult.UPDATED
    stored = repo.list_all()
    assert len(stored) == 1
    assert stored[0].id == "a"               # original id preserved
    assert stored[0].salary_range == "$200k" # field updated


def test_upsert_reopens_a_closed_job(repo):
    repo.upsert(_job("a"))
    closed = repo.list_all()[0].id
    repo.mark_closed([closed])
    repo.upsert(_job("b"))                    # same identity re-seen
    assert repo.list_all()[0].status == "open"
```

If `test_jobs_repository.py` has no `repo` fixture, add one using the existing in-file sqlite session factory pattern (mirror how other tests in that file build `JobsRepository(session_factory=..., bucket="boards")`).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_jobs_repository.py -k upsert -v`
Expected: FAIL — `upsert`/`mark_closed`/`UpsertResult` missing.

> **⚠ Dependency:** `bump_missed_and_close` below delegates to Task 9's
> `detect_closures`/`OpenJob`. Implement **Task 9 before this task's Step 6**
> (the pure detector is the single source of the threshold rule — the repo does
> not re-implement it).

- [ ] **Step 3: Implement `UpsertResult`**

```python
# backend/src/hiresense/ingestion/domain/upsert_result.py
from __future__ import annotations

from enum import Enum


class UpsertResult(str, Enum):
    INSERTED = "inserted"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
```

Re-export from `domain/__init__.py` and add to `__all__`.

- [ ] **Step 4: Implement the shared `identity_key` helper**

Create `backend/src/hiresense/ingestion/domain/identity.py` (used by the
repository AND the orchestrator/scanner, so it lives in `domain`, not a private
repo helper):

```python
# backend/src/hiresense/ingestion/domain/identity.py
from __future__ import annotations

import hashlib

from hiresense.ingestion.domain.models import NormalizedJob


def identity_key(job: NormalizedJob) -> str:
    """Stable identity: source_id (hashed if >64 chars) else sha256(url)."""
    if job.source_id:
        if len(job.source_id) <= 64:
            return job.source_id
        return hashlib.sha256(job.source_id.encode("utf-8")).hexdigest()
    return hashlib.sha256((job.url or "").encode("utf-8")).hexdigest()
```

Re-export `identity_key` from `domain/__init__.py` and add to `__all__`.

- [ ] **Step 5a: Finalize the ORM schema** (now that the repo will populate `identity_key`)

In `backend/src/hiresense/ingestion/infrastructure/models.py` (Task 3 left these transitional):
- Remove the `dedup_key` column and the `UniqueConstraint("bucket","dedup_key", name="ux_ingested_jobs_bucket_dedup")`.
- Tighten `identity_key` to `Mapped[str] = mapped_column(String(64), nullable=False)`.
- Add the new constraint to `__table_args__`: `UniqueConstraint("bucket", "source", "identity_key", name="ux_ingested_jobs_bucket_source_identity")`.

This is safe because the same commit switches `_to_orm` to always set `identity_key` (below), so inserts never leave it null.

- [ ] **Step 5b: Implement repository changes**

In `jobs_repository.py`:

```python
from datetime import datetime, timezone

from hiresense.ingestion.domain.closure_detector import OpenJob, detect_closures
from hiresense.ingestion.domain.content_hash import content_hash
from hiresense.ingestion.domain.identity import identity_key
from hiresense.ingestion.domain.upsert_result import UpsertResult
```

Update `_to_orm` to set `identity_key=identity_key(job)`, `source_id=job.source_id`, `status=job.status`, `content_hash=content_hash(job)`, and drop the `dedup_key=` assignment. Update `_to_domain` to read `source_id=row.source_id`, `status=row.status`. Remove the now-unused `dedup_key` param/logic.

Replace `add_if_absent` with `upsert` (keep a thin `add_if_absent` delegating to `upsert(...) != UNCHANGED` only if other callers still need a bool — but Task 6 migrates them, so remove `add_if_absent`):

```python
    def upsert(self, job: NormalizedJob) -> UpsertResult:
        ident = identity_key(job)
        new_hash = content_hash(job)
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            row = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.source == job.source,
                    IngestedJob.identity_key == ident,
                )
            ).first()
            if row is None:
                session.add(_to_orm(job, self._bucket))  # computes ident + hash internally
                session.commit()
                return UpsertResult.INSERTED

            row.last_seen_at = now
            row.missed_count = 0
            reopened = row.status == "closed"
            if reopened:
                row.status = "open"
                row.closed_at = None

            if row.content_hash != new_hash:
                row.title = job.title
                row.company = job.company
                row.description = job.description
                row.location = job.location
                row.salary_range = job.salary_range
                row.skills = list(job.skills)
                row.categories = list(job.categories)
                row.countries = list(job.countries)
                row.remote_modality = job.remote_modality
                row.content_hash = new_hash
                row.updated_at = now
                session.commit()
                return UpsertResult.UPDATED

            session.commit()
            return UpsertResult.UNCHANGED

    def get_id_by_identity(self, source: str, job: NormalizedJob) -> str | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.source == source,
                    IngestedJob.identity_key == identity_key(job),
                )
            ).first()
            return row.id if row else None

    def mark_closed(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            for row in session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket, IngestedJob.id.in_(job_ids)
                )
            ).all():
                row.status = "closed"
                row.closed_at = now
            session.commit()

    def bump_missed_and_close(self, source: str, seen_identity_keys: set[str], threshold: int) -> list[str]:
        """Apply the disappearance rule to open jobs of `source`. Delegates the
        decision to the pure `detect_closures` (Task 9), then persists. Returns
        ids closed this run."""
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            rows = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.source == source,
                    IngestedJob.status == "open",
                )
            ).all()
            updated, to_close = detect_closures(
                seen=seen_identity_keys,
                open_jobs=[OpenJob(r.id, r.identity_key, r.missed_count) for r in rows],
                threshold=threshold,
            )
            close_set = set(to_close)
            for row in rows:
                row.missed_count = updated[row.id]
                if row.id in close_set:
                    row.status = "closed"
                    row.closed_at = now
            session.commit()
        return to_close
```

Update `_to_orm` signature to `_to_orm(job, bucket)` and compute `identity_key(job)` / `content_hash(job)` inside it; set the new fields; let `last_seen_at` fall to the server default at insert.

- [ ] **Step 6: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_jobs_repository.py -v`
Expected: PASS (including the 3 new upsert tests).

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/upsert_result.py backend/src/hiresense/ingestion/domain/identity.py backend/src/hiresense/ingestion/domain/__init__.py backend/src/hiresense/ingestion/infrastructure/models.py backend/src/hiresense/ingestion/infrastructure/jobs_repository.py backend/tests/unit/ingestion/test_jobs_repository.py
git commit -m "feat(ingestion): identity-keyed upsert + closure methods on JobsRepository"
```

---

## Task 6: In-memory repository parity

**Files:**
- Modify: `backend/src/hiresense/ingestion/infrastructure/in_memory_jobs_repository.py`
- Test: `backend/tests/unit/ingestion/test_jobs_repository.py` (parametrize over both repos, or add a small mirror test)

- [ ] **Step 1: Write the failing test**

Add a test that builds the in-memory repo and runs the same insert→unchanged→update→reopen sequence as Task 5 (copy the three asserts, pointed at the in-memory repo).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_jobs_repository.py -k memory -v`
Expected: FAIL — no `upsert` on in-memory repo.

- [ ] **Step 3: Implement**

Mirror the Task 5 surface in `in_memory_jobs_repository.py` using a dict keyed by `(bucket, source, identity_key)` and storing `NormalizedJob` plus `content_hash`, `status`, `missed_count`. Implement `upsert`, `mark_closed`, `bump_missed_and_close` (delegating to `detect_closures`, same as the DB repo), and `get_id_by_identity` with the same semantics (preserve stored id on update; reopen on re-seen). Import `identity_key` from `hiresense.ingestion.domain.identity`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_jobs_repository.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/infrastructure/in_memory_jobs_repository.py backend/tests/unit/ingestion/test_jobs_repository.py
git commit -m "feat(ingestion): in-memory repository upsert + closure parity"
```

---

## Task 7: Port surface + `supports_snapshot_closure`

**Files:**
- Modify: `backend/src/hiresense/ingestion/ports/jobs_repository.py`
- Modify: `backend/src/hiresense/ingestion/ports/job_source.py`

- [ ] **Step 1: Update `JobsRepositoryPort`**

Replace `add_if_absent` with the new surface:

```python
    def upsert(self, job: NormalizedJob) -> "UpsertResult": ...
    def get_id_by_identity(self, source: str, job: NormalizedJob) -> str | None: ...
    def mark_closed(self, job_ids: list[str]) -> None: ...
    def bump_missed_and_close(self, source: str, seen_identity_keys: set[str], threshold: int) -> list[str]: ...
```

Import `UpsertResult` under `TYPE_CHECKING`. Keep `list_all`, `get_by_id`, `update_scores`, `prune_older_than`.

- [ ] **Step 2: Update `JobSourcePort`**

```python
    def supports_snapshot_closure(self) -> bool:
        """True if one fetch returns the source's COMPLETE current open set,
        so a previously-seen job missing from results implies it closed."""
        ...
```

- [ ] **Step 3: Verify import**

Run: `cd backend && uv run python -c "import hiresense.ingestion.ports"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/ingestion/ports/jobs_repository.py backend/src/hiresense/ingestion/ports/job_source.py
git commit -m "feat(ingestion): lifecycle + snapshot-closure on repository/source ports"
```

---

## Task 8: Indexer `remove`

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/job_embedding_indexer.py`
- Test: `backend/tests/unit/ingestion/test_job_embedding_indexer.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/unit/ingestion/test_job_embedding_indexer.py
import pytest


class _FakeStore:
    def __init__(self): self.deleted = []
    async def upsert(self, *a, **k): ...
    async def delete(self, ids): self.deleted.append(list(ids))


@pytest.mark.asyncio
async def test_remove_deletes_from_vector_store():
    from hiresense.ingestion.domain.job_embedding_indexer import JobEmbeddingIndexer
    store = _FakeStore()
    idx = JobEmbeddingIndexer(embedding=None, vector_store=store, bucket="boards")
    await idx.remove(["j1", "j2"])
    assert store.deleted == [["j1", "j2"]]


@pytest.mark.asyncio
async def test_remove_noop_on_empty():
    from hiresense.ingestion.domain.job_embedding_indexer import JobEmbeddingIndexer
    store = _FakeStore()
    idx = JobEmbeddingIndexer(embedding=None, vector_store=store, bucket="boards")
    await idx.remove([])
    assert store.deleted == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_embedding_indexer.py -k remove -v`
Expected: FAIL — no `remove`.

- [ ] **Step 3: Implement**

```python
    async def remove(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        try:
            await self._vector_store.delete(job_ids)
        except Exception:
            logger.exception("Vector delete failed (n=%d)", len(job_ids))
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_embedding_indexer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_embedding_indexer.py backend/tests/unit/ingestion/test_job_embedding_indexer.py
git commit -m "feat(ingestion): indexer remove() to drop closed jobs from vector store"
```

---

## Task 9: `ClosureDetector` pure helper

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/closure_detector.py`
- Test: `backend/tests/unit/ingestion/test_closure_detector.py`

The detector is the testable core of the disappearance rule, independent of the DB. It takes the set of identity keys seen this run and the current open jobs (as `OpenJob` records) and returns `(updated_missed: dict[id->int], to_close: list[id])`. **`JobsRepository.bump_missed_and_close` (Task 5) delegates to this — it is the single implementation of the rule, so implement this task before Task 5's Step 6.** (Listed after Task 5 for narrative flow; the dependency note in Task 5 flags the ordering.)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/ingestion/test_closure_detector.py
from __future__ import annotations

from hiresense.ingestion.domain.closure_detector import OpenJob, detect_closures


def test_seen_resets_missed_count():
    upd, close = detect_closures(
        seen={"k1"}, open_jobs=[OpenJob("j1", "k1", missed_count=1)], threshold=2,
    )
    assert upd["j1"] == 0 and close == []


def test_missing_increments_below_threshold():
    upd, close = detect_closures(
        seen=set(), open_jobs=[OpenJob("j1", "k1", missed_count=0)], threshold=2,
    )
    assert upd["j1"] == 1 and close == []


def test_missing_at_threshold_closes():
    upd, close = detect_closures(
        seen=set(), open_jobs=[OpenJob("j1", "k1", missed_count=1)], threshold=2,
    )
    assert close == ["j1"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_closure_detector.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# backend/src/hiresense/ingestion/domain/closure_detector.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenJob:
    id: str
    identity_key: str
    missed_count: int


def detect_closures(
    *, seen: set[str], open_jobs: list[OpenJob], threshold: int
) -> tuple[dict[str, int], list[str]]:
    """Pure disappearance rule. Returns (new missed_count per job, ids to close).

    Caller must ONLY invoke this for snapshot-capable sources after a SUCCESSFUL
    fetch (empty allowed). A job seen this run resets to 0; a missing job
    increments and closes once it reaches `threshold`.
    """
    updated: dict[str, int] = {}
    to_close: list[str] = []
    for job in open_jobs:
        if job.identity_key in seen:
            updated[job.id] = 0
            continue
        nxt = job.missed_count + 1
        updated[job.id] = nxt
        if nxt >= threshold:
            to_close.append(job.id)
    return updated, to_close
```

> The DB-backed `bump_missed_and_close` (Task 5) is the persistence-side mirror of this rule; the repository test covers the SQL path, this covers the pure decision logic. They share the same threshold semantics.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_closure_detector.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/closure_detector.py backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/ingestion/test_closure_detector.py
git commit -m "feat(ingestion): pure ClosureDetector disappearance rule"
```

---

## Task 10: Snapshot flags on adapters + default on others

**Files:**
- Modify: `greenhouse_adapter.py`, `lever_adapter.py`, `ashby_adapter.py` (→ `True`)
- Modify: all other adapters OR add a default — simplest: add `supports_snapshot_closure` to a shared base/mixin. Since adapters are plain classes (no shared base), add the method returning `False` to each non-portal adapter, and `True` to the three portal adapters.
- Test: `backend/tests/unit/ingestion/test_greenhouse.py` (append) + one board adapter test.

- [ ] **Step 1: Write the failing tests**

```python
# append to test_greenhouse.py
def test_greenhouse_supports_snapshot_closure():
    a = GreenhouseAdapter(http_client=None, base_url="https://x", timeout=1.0)
    assert a.supports_snapshot_closure() is True

# append to test_remotive.py
def test_remotive_does_not_support_snapshot_closure():
    from hiresense.ingestion.adapters import RemotiveAdapter
    a = RemotiveAdapter(http_client=None)
    assert a.supports_snapshot_closure() is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_greenhouse.py tests/unit/ingestion/test_remotive.py -k snapshot -v`
Expected: FAIL — method missing.

- [ ] **Step 3: Implement**

Add to each portal adapter:
```python
    def supports_snapshot_closure(self) -> bool:
        return True
```
Add to every non-portal adapter (remotive, remoteok, csv, jobicy, himalayas, hn_hiring, weworkremotely, getonboard, linkedin):
```python
    def supports_snapshot_closure(self) -> bool:
        return False
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion -k snapshot -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/adapters/
git add backend/tests/unit/ingestion/test_greenhouse.py backend/tests/unit/ingestion/test_remotive.py
git commit -m "feat(ingestion): declare snapshot-closure capability per adapter"
```

---

## Task 11: Wire upsert + disappearance into `IngestionOrchestrator`

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/services.py:57-92` and `:94-95`
- Test: `backend/tests/unit/ingestion/test_orchestrator.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to test_orchestrator.py — uses in-memory repo + fakes already in that file
@pytest.mark.asyncio
async def test_closes_job_missing_from_snapshot_source_after_threshold(...):
    # source.supports_snapshot_closure() == True, threshold default 2.
    # Run 1: source returns [jobA, jobB]; both stored open.
    # Run 2: source returns [jobA]; jobB missed_count -> 1 (still open).
    # Run 3: source returns [jobA]; jobB missed_count -> 2 -> closed.
    # Assert repo job B status == "closed", and indexer.remove called with [B.id].
    ...

@pytest.mark.asyncio
async def test_non_snapshot_source_never_closes(...):
    # supports_snapshot_closure() == False; jobB missing for many runs -> stays open.
    ...

@pytest.mark.asyncio
async def test_changed_job_is_reindexed(...):
    # Run 2 returns jobA with new salary -> UPDATED -> indexer.index called with the row id reused.
    ...
```

(Flesh these out with the file's existing fake-source / in-memory-repo helpers; mirror their construction.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_orchestrator.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Add `closure_miss_threshold: int = 2` to `IngestionOrchestrator.__init__`. Rewrite the per-source body of `run`:

```python
            try:
                raw_jobs = await source.fetch_jobs(filters)
            except Exception:
                logger.exception("Failed to fetch from %s", source_name)
                continue  # bad fetch: skip disappearance for this source this run

            seen_keys: set[str] = set()
            touched: list[NormalizedJob] = []
            for raw in raw_jobs:
                normalized_data = normalizer.normalize(raw)
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=source_name,
                    source_type=source.source_type().value,
                    source_id=raw.source_id,
                    **normalized_data,
                )
                existing_id = self._repository.get_id_by_identity(source_name, job)
                if existing_id:
                    job = job.model_copy(update={"id": existing_id})
                seen_keys.add(identity_key(job))  # from hiresense.ingestion.domain.identity
                result = self._repository.upsert(job)
                if result in (UpsertResult.INSERTED, UpsertResult.UPDATED):
                    touched.append(job)
                    if result == UpsertResult.INSERTED:
                        new_jobs.append(job)

            # Re-index inserted AND updated jobs (same id reused on update).
            if touched and self._indexer is not None:
                await self._indexer.index(touched)

            # Disappearance-based closure (snapshot sources only, fetch succeeded).
            if source.supports_snapshot_closure():
                closed_ids = self._repository.bump_missed_and_close(
                    source_name, seen_keys, self._closure_miss_threshold
                )
                if closed_ids and self._indexer is not None:
                    await self._indexer.remove(closed_ids)
```

Import `UpsertResult` from `hiresense.ingestion.domain.upsert_result` and `identity_key` from `hiresense.ingestion.domain.identity` (both created in Task 5). Update `store_job` (`services.py:94`) to call `self._repository.upsert(job)` instead of `add_if_absent`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_orchestrator.py tests/unit/ingestion/test_jobs_repository.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/services.py backend/tests/unit/ingestion/test_orchestrator.py
git commit -m "feat(ingestion): upsert + disappearance closure in orchestrator"
```

---

## Task 12: Wire upsert + disappearance into `PortalScanner`

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/portal_scanner.py:98-165`
- Test: `backend/tests/unit/ingestion/test_portal_scanner.py` (append)

- [ ] **Step 1: Write the failing test**

Mirror Task 11's closure test for the scanner: a portal (`source = portal.name`) whose adapter `supports_snapshot_closure()` is True; a job present in scan 1 and missing in scans 2–3 ends `closed`; `ScanResult.duplicates` still computed; `indexer.remove` called.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_portal_scanner.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Add `closure_miss_threshold: int = 2` to `PortalScanner.__init__`. In `scan`, per portal: build `seen_keys`, set `job.source_id = raw.source_id`, look up existing id and reuse, call `upsert`, collect `INSERTED`/`UPDATED` into a `touched` list (and `INSERTED` into `new_jobs`), index `touched`. After the per-portal loop iteration, if `adapter.supports_snapshot_closure()`, call `bump_missed_and_close(portal.name, seen_keys, threshold)` and `indexer.remove(closed_ids)`. Recompute `duplicates = total_fetched - len(new_jobs)`.

> Note: scope closure per `portal.name` (the `source`), not per platform — each company board is its own complete snapshot. Run closure even when a portal returns zero jobs (legit "no open roles"), but only when the fetch did not raise (the existing `except` path `continue`s before reaching closure).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_portal_scanner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/portal_scanner.py backend/tests/unit/ingestion/test_portal_scanner.py
git commit -m "feat(ingestion): upsert + disappearance closure in portal scanner"
```

---

## Task 13: `include_closed` filter + API `status`

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/job_filter.py:18-48` and `:50-95`
- Modify: `backend/src/hiresense/ingestion/api/routes.py:175` (build params) + response model
- Test: `backend/tests/unit/ingestion/test_job_filter.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to test_job_filter.py
def test_closed_hidden_by_default():
    jobs = [_job(status="open"), _job(status="closed")]   # _job helper in this file
    out = filter_and_paginate(jobs, JobQueryParams())
    assert all(j.status == "open" for j in out.jobs)
    assert out.total == 1


def test_include_closed_shows_all():
    jobs = [_job(status="open"), _job(status="closed")]
    out = filter_and_paginate(jobs, JobQueryParams(include_closed=True))
    assert out.total == 2
```

If the file's `_job` helper doesn't set `status`, extend it to pass through `status`.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_filter.py -k closed -v`
Expected: FAIL — no `include_closed`.

- [ ] **Step 3: Implement**

In `JobQueryParams` add `include_closed: bool = False`. In `filter_and_paginate`, as the first filter:

```python
    if not params.include_closed:
        filtered = [j for j in filtered if j.status != "closed"]
```

In `routes.py`, add `include_closed: bool = False` to the list endpoint query params and pass it into `JobQueryParams(...)`. Ensure the API job response model includes `status` (it already serializes from `NormalizedJob`; add `status` to the response schema if it's an explicit pydantic model).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_filter.py tests/unit/ingestion/test_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_filter.py backend/src/hiresense/ingestion/api/routes.py backend/tests/unit/ingestion/test_job_filter.py
git commit -m "feat(ingestion): hide closed jobs by default with include_closed override"
```

---

## Task 14: Retention bump (config)

**Files:**
- Modify: `backend/src/hiresense/config.py:109`
- Modify: `backend/.env.example:46`

- [ ] **Step 1: Change default and example**

`config.py`: `ingestion_job_retention_days: int = 90` (update the comment to note closure is now the primary lifecycle signal; age-pruning is the GC backstop).
`.env.example`: `INGESTION_JOB_RETENTION_DAYS=90`.

- [ ] **Step 2: Verify config loads**

Run: `cd backend && uv run python -c "from hiresense.config import Settings; print(Settings().ingestion_job_retention_days)"`
Expected: `90`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "chore(ingestion): raise job retention to 90d (closure is primary signal)"
```

---

## Task 15: Frontend — Closed badge + "Show closed" toggle

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts`
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.html` (the job-card list)
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.scss`

- [ ] **Step 1: Add the `status` field to the job interface**

Add `status?: 'open' | 'closed';` to the TS job model used by this page. Add `includeClosed = false;` component state and an `include_closed` query param when calling the list API.

- [ ] **Step 2: Add the toggle + badge to the template**

Add a "Show closed" checkbox bound to `includeClosed` that re-fetches on change. On each job card, render a `Closed` badge when `job.status === 'closed'` and add a `closed` CSS class to dim the card.

- [ ] **Step 3: Style**

Add `.job-card.closed { opacity: .6; }` and a `.badge-closed` style consistent with existing badges in the scss.

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/ingestion/
git commit -m "feat(ingestion-ui): closed-job badge and show-closed toggle"
```

---

## Phase 1 checkpoint

Run the full backend ingestion suite:

Run: `cd backend && uv run python -m pytest tests/unit/ingestion -v`
Expected: all green. At this point: change-detection works on every source, portals/snapshot sources detect closures by disappearance, closed jobs are hidden by default + dropped from the vector index, and the UI badges them.

---

# PHASE 2 — Throttled URL-probe revalidation sweep

## Task 16: `ClosedListingClassifier` pure helper

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/closed_listing_classifier.py`
- Test: `backend/tests/unit/ingestion/test_closed_listing_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/ingestion/test_closed_listing_classifier.py
from __future__ import annotations

from hiresense.ingestion.domain.closed_listing_classifier import (
    Verdict, classify_listing,
)

MARKERS = ["no longer accepting", "position has been filled", "this job is closed", "ya no está disponible"]


def test_404_is_closed():
    assert classify_listing(status_code=404, body="", markers=MARKERS) == Verdict.CLOSED


def test_410_is_closed():
    assert classify_listing(status_code=410, body="x", markers=MARKERS) == Verdict.CLOSED


def test_200_with_marker_is_closed():
    body = "<h1>This Job Is Closed</h1>"
    assert classify_listing(status_code=200, body=body, markers=MARKERS) == Verdict.CLOSED


def test_200_plain_is_open():
    assert classify_listing(status_code=200, body="Apply now!", markers=MARKERS) == Verdict.OPEN


def test_5xx_is_unknown():
    assert classify_listing(status_code=503, body="", markers=MARKERS) == Verdict.UNKNOWN
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_closed_listing_classifier.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# backend/src/hiresense/ingestion/domain/closed_listing_classifier.py
from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


def classify_listing(*, status_code: int, body: str, markers: list[str]) -> Verdict:
    """Map an HTTP probe result to a lifecycle verdict.

    404/410 -> CLOSED. 200 + a closed-marker phrase -> CLOSED. 200 plain ->
    OPEN. Anything else (5xx, timeouts surfaced as None upstream -> caller maps
    to UNKNOWN) -> UNKNOWN; UNKNOWN never closes a job.
    """
    if status_code in (404, 410):
        return Verdict.CLOSED
    if status_code == 200:
        low = body.lower()
        if any(m.lower() in low for m in markers):
            return Verdict.CLOSED
        return Verdict.OPEN
    return Verdict.UNKNOWN
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_closed_listing_classifier.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/closed_listing_classifier.py backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/ingestion/test_closed_listing_classifier.py
git commit -m "feat(ingestion): pure ClosedListingClassifier for URL probes"
```

---

## Task 17: Repository `find_open_stale` (sweep selection)

**Files:**
- Modify: `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py` + in-memory mirror + port
- Test: `backend/tests/unit/ingestion/test_jobs_repository.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_find_open_stale_orders_oldest_checked_first_and_caps(repo):
    # insert 3 open jobs; set last_checked_at: j1=None, j2=old, j3=recent
    # find_open_stale(sources=["remotive"], limit=2) -> [j1, j2] (NULLS first, then oldest)
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_jobs_repository.py -k stale -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
    def find_open_stale(self, sources: list[str], limit: int) -> list[NormalizedJob]:
        with self._session_factory() as session:
            stmt = (
                select(IngestedJob)
                .where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.status == "open",
                    IngestedJob.source.in_(sources),
                )
                .order_by(IngestedJob.last_checked_at.asc().nullsfirst())
                .limit(limit)
            )
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def mark_checked(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            for row in session.scalars(
                select(IngestedJob).where(IngestedJob.id.in_(job_ids))
            ).all():
                row.last_checked_at = now
            session.commit()
```

Add both to the port and the in-memory repo (in-memory: sort by `last_checked_at or datetime.min`). `nullsfirst` is Postgres; sqlite tests: `nullsfirst()` is emitted but sqlite treats NULL as lowest already — acceptable; if the test is sqlite-backed, assert on the set rather than strict order for the NULL/old pair, or seed all three with explicit timestamps and a 4th with NULL.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_jobs_repository.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/infrastructure/jobs_repository.py backend/src/hiresense/ingestion/infrastructure/in_memory_jobs_repository.py backend/src/hiresense/ingestion/ports/jobs_repository.py backend/tests/unit/ingestion/test_jobs_repository.py
git commit -m "feat(ingestion): find_open_stale + mark_checked for revalidation sweep"
```

---

## Task 18: `JobRevalidationService`

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/job_revalidation_service.py`
- Test: `backend/tests/unit/ingestion/test_job_revalidation_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/ingestion/test_job_revalidation_service.py
from __future__ import annotations

import pytest


class _Resp:
    def __init__(self, code, text=""): self.status_code = code; self.text = text


class _Client:
    def __init__(self, by_url): self._by_url = by_url
    async def get(self, url, **k): return self._by_url[url]


@pytest.mark.asyncio
async def test_sweep_closes_404_and_marks_checked(in_memory_repo_with_two_open_jobs):
    repo, jobA, jobB = in_memory_repo_with_two_open_jobs  # jobA.url, jobB.url
    client = _Client({jobA.url: _Resp(200, "Apply now"), jobB.url: _Resp(404)})
    closed_ids = []
    class _Idx:
        async def remove(self, ids): closed_ids.extend(ids)
    from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=_Idx(),
        sources=[jobA.source], markers=["closed"], batch=10, concurrency=2, delay=0.0,
    )
    await svc.sweep()
    statuses = {j.id: j.status for j in repo.list_all()}
    assert statuses[jobB.id] == "closed"
    assert statuses[jobA.id] == "open"
    assert closed_ids == [jobB.id]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_revalidation_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# backend/src/hiresense/ingestion/domain/job_revalidation_service.py
from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.ingestion.domain.closed_listing_classifier import Verdict, classify_listing

logger = logging.getLogger(__name__)


class JobRevalidationService:
    """Throttled URL-probe sweep that closes dead listings for feed/search sources."""

    def __init__(
        self, *, http_client: Any, repository: Any, indexer: Any | None,
        sources: list[str], markers: list[str], batch: int,
        concurrency: int, delay: float,
    ) -> None:
        self._http = http_client
        self._repo = repository
        self._indexer = indexer
        self._sources = sources
        self._markers = markers
        self._batch = batch
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._delay = delay

    async def sweep(self) -> list[str]:
        jobs = self._repo.find_open_stale(self._sources, self._batch)
        if not jobs:
            return []
        verdicts = await asyncio.gather(*(self._probe(j) for j in jobs))
        to_close = [j.id for j, v in zip(jobs, verdicts) if v == Verdict.CLOSED]
        self._repo.mark_checked([j.id for j in jobs])
        if to_close:
            self._repo.mark_closed(to_close)
            if self._indexer is not None:
                await self._indexer.remove(to_close)
        logger.info("Revalidation sweep: probed %d, closed %d", len(jobs), len(to_close))
        return to_close

    async def _probe(self, job: Any) -> Verdict:
        async with self._sem:
            try:
                resp = await self._http.get(job.url, follow_redirects=True)
            except Exception:
                return Verdict.UNKNOWN
            finally:
                if self._delay:
                    await asyncio.sleep(self._delay)
            return classify_listing(
                status_code=resp.status_code, body=getattr(resp, "text", "") or "",
                markers=self._markers,
            )
```

Add the test fixture `in_memory_repo_with_two_open_jobs` to the test file (build the in-memory repo, upsert two open jobs with distinct urls/source_ids, return them).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_revalidation_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_revalidation_service.py backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/ingestion/test_job_revalidation_service.py
git commit -m "feat(ingestion): JobRevalidationService throttled URL-probe sweep"
```

---

## Task 19: Phase 2 config keys

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add settings**

In `config.py`:

```python
    # Job closure / revalidation
    job_closure_miss_threshold: int = 2
    job_revalidation_interval_hours: int = 24
    job_revalidation_batch: int = 100
    job_revalidation_concurrency: int = 2
    job_revalidation_delay: float = 1.0
    # Phrases (lowercased substring match) signalling a 200-OK page is actually closed.
    job_closed_markers: list[str] = [
        "no longer accepting applications",
        "position has been filled",
        "this job is closed",
        "this position is no longer available",
        "ya no está disponible",
        "esta oferta ya no está disponible",
    ]
```

In `.env.example`, add the scalar keys with placeholder values and a comment (list-valued `JOB_CLOSED_MARKERS` documented as comma/JSON per the project's existing list-env convention — match how `getonboard_categories`/`supported_languages` are expressed in `.env.example`).

- [ ] **Step 2: Verify config loads**

Run: `cd backend && uv run python -c "from hiresense.config import Settings; s=Settings(); print(s.job_closure_miss_threshold, len(s.job_closed_markers))"`
Expected: `2 6`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(ingestion): config for closure threshold + revalidation sweep"
```

---

## Task 20: Wire threshold + revalidation into bootstrap + trigger endpoint

**Files:**
- Modify: `backend/src/hiresense/bootstrap/ingestion.py`
- Modify: `backend/src/hiresense/ingestion/api/routes.py` (manual trigger)
- Test: `backend/tests/unit/ingestion/test_scan_routes.py` or `test_routes.py` (append a trigger test)

- [ ] **Step 1: Pass the threshold into orchestrator + scanner**

In `bootstrap/ingestion.py`, pass `closure_miss_threshold=s.job_closure_miss_threshold` to both `IngestionOrchestrator(...)` and `PortalScanner(...)`.

- [ ] **Step 2: Construct `JobRevalidationService` instances**

Build one per bucket (boards/portals), passing `http_client=infra.http_client`, the matching repo, the matching indexer, `sources=[non-snapshot source names for that bucket]`, and the config knobs. For boards, `sources` = the enabled non-snapshot source names (everything except none — all boards are non-snapshot; exclude `hn_hiring` since its URLs never 404 / have no marker — HN closes via age backstop). For portals, the sweep is unnecessary (snapshot disappearance covers them) — skip wiring a portals sweep.

- [ ] **Step 3: Add a manual trigger endpoint**

Add `POST /ingestion/revalidate` to `routes.py` that calls `await revalidation_service.sweep()` and returns `{"closed": <count>}`. (Scheduling: this repo has no scheduler yet; the endpoint lets a cron/external trigger drive the daily sweep. A background scheduler is out of scope for this plan — documented in the spec's "Scheduling" note.)

- [ ] **Step 4: Write + run the trigger test**

Add a route test that posts to `/ingestion/revalidate` with a fake service and asserts the JSON shape.
Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_routes.py -k revalidate -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/bootstrap/ingestion.py backend/src/hiresense/ingestion/api/routes.py backend/tests/unit/ingestion/test_routes.py
git commit -m "feat(ingestion): wire revalidation sweep + manual trigger endpoint"
```

---

## Final checkpoint

Run: `cd backend && uv run python -m pytest -q`
Expected: full suite green.

Run: `cd frontend && npm run build`
Expected: build succeeds.

Manual smoke (optional): run the app, trigger `/ingestion/fetch` twice with a source that drops a job between runs, confirm the job flips to `closed` after the threshold and disappears from the default list but appears with "Show closed".
