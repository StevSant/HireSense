# Phase 4 (LinkedIn Network) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import LinkedIn's `Connections.csv` (from the data-export ZIP) into a new `network` bounded context, and surface "you know someone at this company": a connections badge on the jobs list and contact suggestions on the outreach page.

**Scope decision:** Part B of the spec has two halves. This PR ships the **high-value half** (connections → network context → badges + outreach suggestions). The Positions/Skills/Education → profile merge is deferred to its own follow-up: profiles are per-language CV-derived rows with no data-lineage tagging today, and bolting LinkedIn rows onto them without an origin model would make re-imports destructive. Recorded in the spec's terms — additive, idempotent merge needs the origin field design first.

**Privacy invariant (from the spec):** contacts live only in the local DB and are NEVER injected into LLM prompts. Badges and matching are deterministic lookups. The only path into a prompt is the existing user-initiated `contact_name` field, which the user fills (suggestions just pre-fill the input).

**Working directory:** `C:\Users\Bryan\worktrees\hiresense-portfolio` (branch `feat/network-linkedin`, stacked on `feat/portfolio-citation`; PR base = that branch). **Quirks:** `uv run python -m pytest` only; no repo-wide `ruff format`; CI runs `npx ng lint` (run it for frontend tasks); commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

**Verified facts:**
- LinkedIn `Connections.csv` columns: `First Name,Last Name,URL,Email Address,Company,Position,Connected On`. Real exports OFTEN begin with a "Notes:" preamble paragraph before the header — the parser must scan for the header line.
- Upload hardening precedent: `profile/api/routes.py` (`_ALLOWED_EXTENSIONS`, size cap via `settings.max_upload_bytes`, magic-byte sniffing). ZIP magic: `PK\x03\x04`.
- Latest migration: 026 → this PR creates **027**.
- Jobs list: `PaginatedResult` (`ingestion/domain/job_filter.py:55`) — extend with an optional per-job map rather than touching `NormalizedJob`. Frontend rows: `pages/ingestion/ingestion.component.html` `@for (job of jobs(); ...)` with a company cell.
- Outreach frontend: free-text `contact_name` input bound to a signal (`pages/outreach/outreach.component.*`); `GenerateRequest` model.
- Module template: `autohunt`/`portfolio` (api/provider+dependencies+routes, domain one-class-per-file, infrastructure orm+repository, bootstrap builder, registry import).

---

### Task 1: Network domain — Contact + company normalization

**Files:** create `backend/src/hiresense/network/__init__.py` (docstring), `network/domain/contact.py`, `network/domain/company_normalization.py`, `network/domain/__init__.py`; test `backend/tests/unit/network/__init__.py` (empty) + `test_company_normalization.py` + `test_contact.py`

- [ ] **Step 1: failing tests.**

`tests/unit/network/test_company_normalization.py`:

```python
import pytest

from hiresense.network.domain import normalize_company


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme Inc.", "acme"),
        ("ACME, LLC", "acme"),
        ("Globant S.A.", "globant"),
        ("Mercado Libre S.A. de C.V.", "mercado libre"),
        ("Stripe", "stripe"),
        ("  Banco   Guayaquil  ", "banco guayaquil"),
        ("Thoughtworks Ltd", "thoughtworks"),
        ("Siemens GmbH", "siemens"),
        ("MixRank (YC S11)", "mixrank"),
        ("", ""),
    ],
)
def test_normalize_company(raw: str, expected: str) -> None:
    assert normalize_company(raw) == expected
```

`tests/unit/network/test_contact.py`:

```python
from hiresense.network.domain import Contact


def test_contact_normalizes_company_on_construction() -> None:
    contact = Contact(
        first_name="Jordan", last_name="Lee", company="Acme Inc.", position="EM"
    )
    assert contact.company_normalized == "acme"
    assert contact.linkedin_url is None
    assert contact.email is None


def test_contact_empty_company_normalizes_empty() -> None:
    assert Contact(first_name="A", last_name="B", company="").company_normalized == ""
```

- [ ] **Step 2:** run `uv run python -m pytest tests/unit/network -q` → FAIL.

- [ ] **Step 3: implement.**

`network/__init__.py`: `"""Network bounded context — contacts imported from LinkedIn exports."""`

`network/domain/company_normalization.py`:

```python
from __future__ import annotations

import re

# Legal-suffix tokens stripped from the END of company names, repeatedly
# ("Acme Holdings Inc." -> "acme holdings"). Lowercase, dot-free forms.
_LEGAL_SUFFIXES = frozenset(
    {
        "inc", "incorporated", "llc", "llp", "ltd", "limited", "corp",
        "corporation", "co", "company", "gmbh", "sa", "sas", "srl", "sl",
        "bv", "ag", "plc", "sa de cv", "cv", "de",
    }
)
_PARENS_RE = re.compile(r"\([^)]*\)")
_NON_WORD_RE = re.compile(r"[^a-z0-9 ]+")
_SPACES_RE = re.compile(r"\s+")


def normalize_company(raw: str) -> str:
    """Canonical company key for matching contacts to job postings.

    Lowercases, drops parentheticals and punctuation, collapses whitespace,
    and strips trailing legal suffixes (inc/llc/s.a./gmbh/...).
    """
    text = _PARENS_RE.sub(" ", raw.lower())
    text = _NON_WORD_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text).strip()
    words = text.split(" ") if text else []
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)
```

`network/domain/contact.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, model_validator

from hiresense.network.domain.company_normalization import normalize_company


class Contact(BaseModel):
    """One LinkedIn connection. company_normalized is derived, never set by hand."""

    first_name: str
    last_name: str
    company: str = ""
    position: str = ""
    linkedin_url: str | None = None
    email: str | None = None
    connected_on: str | None = None
    company_normalized: str = ""

    @model_validator(mode="after")
    def _derive_company_normalized(self) -> "Contact":
        object.__setattr__(self, "company_normalized", normalize_company(self.company))
        return self
```

`network/domain/__init__.py` re-exports `Contact`, `normalize_company` with `__all__`.

- [ ] **Step 4:** tests pass; `uv run ruff check src/hiresense/network tests/unit/network` clean.
- [ ] **Step 5: commit** — `feat(network): contact model and company normalization`.

---

### Task 2: Connections parser (ZIP or CSV bytes → contacts)

**Files:** create `backend/src/hiresense/network/domain/connections_parser.py`; modify `network/domain/__init__.py`; test `tests/unit/network/test_connections_parser.py`

- [ ] **Step 1: failing tests:**

```python
import io
import zipfile

import pytest

from hiresense.network.domain import ConnectionsParseError, parse_connections

_HEADER = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"
_ROWS = (
    'Jordan,Lee,https://www.linkedin.com/in/jlee,,Acme Inc.,Engineering Manager,01 Feb 2025\n'
    'Sam,Diaz,,sam@x.dev,Globant S.A.,Recruiter,15 Mar 2024\n'
    ',,,,,,\n'  # fully empty row is skipped
)
_PREAMBLE = (
    '"Notes:\nWhen exporting your connection data, you may notice missing emails."\n\n'
)


def _csv_bytes(*, preamble: bool) -> bytes:
    return ((_PREAMBLE if preamble else "") + _HEADER + "\n" + _ROWS).encode("utf-8")


def test_parses_plain_csv_with_preamble() -> None:
    contacts = parse_connections(_csv_bytes(preamble=True), filename="Connections.csv")
    assert len(contacts) == 2
    assert contacts[0].first_name == "Jordan"
    assert contacts[0].company_normalized == "acme"
    assert contacts[1].email == "sam@x.dev"
    assert contacts[1].connected_on == "15 Mar 2024"


def test_parses_csv_without_preamble() -> None:
    assert len(parse_connections(_csv_bytes(preamble=False), filename="x.csv")) == 2


def test_parses_zip_export() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Basic_LinkedInDataExport/Connections.csv", _csv_bytes(preamble=True))
        archive.writestr("Basic_LinkedInDataExport/Skills.csv", "Name\nPython\n")
    contacts = parse_connections(buffer.getvalue(), filename="export.zip")
    assert len(contacts) == 2


def test_zip_without_connections_raises() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Skills.csv", "Name\nPython\n")
    with pytest.raises(ConnectionsParseError, match="Connections.csv"):
        parse_connections(buffer.getvalue(), filename="export.zip")


def test_csv_without_header_raises() -> None:
    with pytest.raises(ConnectionsParseError, match="header"):
        parse_connections(b"not,a,connections,file\n1,2,3,4\n", filename="x.csv")
```

- [ ] **Step 2:** FAIL. **Step 3: implement** `connections_parser.py`:

```python
from __future__ import annotations

import csv
import io
import zipfile

from hiresense.network.domain.contact import Contact

_EXPECTED_COLUMNS = {"First Name", "Last Name", "Company", "Position"}
_ZIP_MAGIC = b"PK\x03\x04"


class ConnectionsParseError(ValueError):
    """Raised when the upload is not a parseable LinkedIn connections export."""


def parse_connections(payload: bytes, *, filename: str) -> list[Contact]:
    """Parse LinkedIn `Connections.csv` content — given directly or inside the
    data-export ZIP. Tolerates LinkedIn's "Notes:" preamble before the header."""
    if payload.startswith(_ZIP_MAGIC):
        payload = _extract_connections_member(payload)
    return _parse_csv(payload)


def _extract_connections_member(payload: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            if name.rsplit("/", 1)[-1].lower() == "connections.csv":
                return archive.read(name)
    raise ConnectionsParseError("ZIP does not contain a Connections.csv")


def _parse_csv(payload: bytes) -> list[Contact]:
    text = payload.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header_index = next(
        (i for i, line in enumerate(lines) if line.startswith("First Name,")), None
    )
    if header_index is None:
        raise ConnectionsParseError("No connections header row found")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    if not _EXPECTED_COLUMNS.issubset(set(reader.fieldnames or [])):
        raise ConnectionsParseError("Connections header is missing expected columns")
    contacts: list[Contact] = []
    for row in reader:
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        if not first and not last:
            continue  # blank padding rows in real exports
        contacts.append(
            Contact(
                first_name=first,
                last_name=last,
                company=(row.get("Company") or "").strip(),
                position=(row.get("Position") or "").strip(),
                linkedin_url=(row.get("URL") or "").strip() or None,
                email=(row.get("Email Address") or "").strip() or None,
                connected_on=(row.get("Connected On") or "").strip() or None,
            )
        )
    return contacts
```

Re-export `parse_connections`, `ConnectionsParseError` from `domain/__init__.py`.

- [ ] **Step 4:** tests + ruff. **Step 5: commit** — `feat(network): LinkedIn connections parser`.

---

### Task 3: Persistence — port, ORM, repository, migration 027

**Files:** create `network/ports/contacts_repository.py` + `network/ports/__init__.py`, `network/infrastructure/orm.py`, `network/infrastructure/repository.py`, `network/infrastructure/__init__.py`; modify `src/hiresense/infrastructure/registry.py`; migration via autogenerate (rename to `027_add_network_contacts.py`, down_revision "026" — VERIFY it contains ONLY this table; the dev DB's known profiles JSONB drift must be stripped if autogenerate picks it up); test `tests/unit/network/test_contacts_repository.py`

Port Protocol:

```python
class ContactsRepositoryPort(Protocol):
    def replace_all(self, contacts: list[Contact]) -> int: ...
    def list_all(self, company: str | None = None) -> list[Contact]: ...
    def find_by_company(self, company_normalized: str) -> list[Contact]: ...
    def count_by_companies(self, companies_normalized: list[str]) -> dict[str, int]: ...
    def last_imported_at(self) -> datetime | None: ...
```

ORM `NetworkContactOrm` → table `network_contacts`: `id` String(64) PK (uuid assigned by repo), first/last_name String(256), company String(512), position String(512), linkedin_url/email String(2048/512) nullable, connected_on String(64) nullable, `company_normalized` String(512) indexed (`ix_network_contacts_company_normalized`), `imported_at` DateTime(tz).

Repository semantics: `replace_all` = delete all + insert (one transaction, the import is a full snapshot — same model as the portfolio sync); `list_all(company=...)` filters by `company_normalized == normalize_company(company)` when given; `count_by_companies` = one GROUP BY query over the given keys returning {key: count}. Tests use the StaticPool sqlite fixture pattern (`create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)`) covering: roundtrip, replace-all idempotency, find_by_company normalization, count_by_companies including absent keys (absent → missing from dict, callers default to 0), last_imported_at None→set.

- [ ] TDD steps as usual; run `tests/unit/network tests/unit/test_orm_registry.py`; generate + prune migration 027 (compose db up; `uv run python -m alembic upgrade head` before and after); ruff. **Commit** — `feat(network): contacts snapshot repository and migration`.

---

### Task 4: API + bootstrap — import, contacts, match

**Files:** create `network/api/provider.py`, `network/api/dependencies.py`, `network/api/routes.py`, `network/api/__init__.py`, `network/domain/import_service.py` (+ re-export); `bootstrap/network.py` (+ bootstrap `__init__` export); modify `main.py`; tests `tests/unit/network/test_import_service.py`, `tests/unit/network/test_routes.py`

`NetworkImportService` (domain): `async import_upload(payload: bytes, filename: str) -> int` — `parse_connections` then `await asyncio.to_thread(repo.replace_all, contacts)`; raises `ConnectionsParseError` through.

Routes (router-level `require_auth`, mirror portfolio's None-degrading dependencies via `app.state.network`):
- `POST /network/import` — `UploadFile`; validation mirroring the hardened profile upload: extension whitelist `{".zip", ".csv"}`, `settings.max_upload_bytes` size cap (413), magic check (`PK\x03\x04` for .zip; for .csv must decode utf-8(-sig)) → 400 on mismatch; `ConnectionsParseError` → 400 with detail; success → `{"contacts": N, "imported_at": ...}`. 503 when module state missing (never happens — network has no external config; ALWAYS built in main.py, so dependencies can assume presence but still degrade gracefully for bare test apps).
- `GET /network/contacts?company=` → list (company optional).
- `GET /network/match?company=<name>` → `{company_normalized, contacts: [...]}` using `find_by_company(normalize_company(company))`.

`bootstrap/network.py`: `build_network(infra) -> NetworkBuild` (always built — no config gate; repo on `infra.sync_session_factory`). `main.py`: build after portfolio, `app.state.network = network.provider`, mount router.

Route tests mirror `tests/unit/portfolio/test_routes.py`: 401 unauth; import happy path (small CSV bytes), import rejects wrong extension/oversized/garbage; contacts list; match normalizes the query. App-boot determinism: network has no env config — nothing to pin.

- [ ] TDD; full suite green; ruff. **Commit** — `feat(network): import and match endpoints`.

---

### Task 5: Jobs-list connections badge (backend)

**Files:** modify `ingestion/domain/job_filter.py` (`PaginatedResult`), `ingestion/api/routes.py`; create `network/api` dependency `get_network_repository` if not already (Task 4 created it); test `tests/unit/ingestion/test_jobs_connections_badge.py`

- `PaginatedResult` gains `connections_by_job: dict[str, int] = {}` (default empty — every existing constructor call stays valid; pydantic default).
- In `list_jobs` (ingestion routes), AFTER `result = filter_and_paginate(...)` and the page-level scoring, add:

```python
    if network_repo is not None and result.jobs:
        keys = {job.id: normalize_company(job.company) for job in result.jobs}
        counts = await asyncio.to_thread(
            network_repo.count_by_companies, sorted({k for k in keys.values() if k})
        )
        result.connections_by_job = {
            job_id: counts[key] for job_id, key in keys.items() if counts.get(key)
        }
```

with `network_repo: Annotated[ContactsRepositoryPort | None, Depends(get_network_repository)]` (import dependency from `hiresense.network.api.dependencies`, `normalize_company` from `hiresense.network.domain`). Page-only computation — one GROUP BY per request, no per-row queries.
- Tests: route-level with a fake repo override → assert `connections_by_job` contains only jobs with matches; absent dependency (bare app) → field `{}` and (critical) existing list tests untouched.

- [ ] TDD; FULL suite; ruff. **Commit** — `feat(network): connections count on the jobs list`.

---

### Task 6: Frontend — network card, jobs badge, outreach suggestions

**Files:**
- create `frontend/src/app/core/services/network.service.ts` (+spec): `import(file: File)` (FormData POST `/network/import`), `match(company: string)`, `contacts()`.
- create `frontend/src/app/pages/profile/models/network-*.model.ts` (import result, contact).
- create `frontend/src/app/pages/profile/components/network-card/` (+spec): mirrors `portfolio-card` — file input (accept `.zip,.csv`), import button with progress/error, "N contacts · last imported …". Mount at the end of `panel-personal` after `<app-portfolio-card />`.
- modify `frontend/src/app/pages/ingestion/` jobs table: model `paginated-result` gains `connections_by_job?: Record<string, number>`; in the company cell render `@if (connectionsFor(job); as n) {<span class="badge connections-badge" [attr.title]="n + ' connections at this company'">{{ n }} 🤝</span>}` — read the actual component/model files first and follow their conventions (the ingestion service maps the response; check where PaginatedResult fields are read).
- modify `frontend/src/app/pages/outreach/`: when an application is selected (there's a signal for the selected application/company — read the component), call `network.match(company)`; render suggestion chips under the contact-name input; clicking a chip sets `contactName` to "First Last". Add spec for the suggestion behavior with HttpTestingController.

- [ ] TDD per component (`npm test -- --include ...`), then full `npm test` AND `npx ng lint`. **Commit** — `feat(network): import card, jobs badge, outreach suggestions`.

---

### Task 7: Verification + smoke + stacked PR

- [ ] Backend full suite + ruff; frontend full tests + `npx ng lint`.
- [ ] Migration 027 applied to compose DB; `-m pgvector` opt-in suite still green.
- [ ] Live smoke: craft a small fake `Connections.csv` (2 rows, one company matching an existing tracked/job company, e.g. "MixRank (YC S11)"); `POST /network/import`; `GET /network/match?company=MixRank (YC S11)` returns the contact; `GET /ingestion/jobs?...` page containing a MixRank job shows `connections_by_job` with its id. (Use the real export later — the user can re-import their actual ZIP from the UI.)
- [ ] Push `feat/network-linkedin`; PR base `feat/portfolio-citation`, title `feat(network): LinkedIn connections import with company-match badges (Phase 4)`. Body: scope decision (profile merge deferred + why), privacy invariant, smoke evidence, Claude Code footer.

## Self-review notes (applied)
- Spec Part B coverage: connections import ✓, badges ✓, outreach targeting ✓, privacy ✓; positions/skills merge consciously deferred (lineage design) — stated in PR + spec terms.
- `count_by_companies` is the only hot-path query; indexed column, page-scoped.
- No env config for the module (upload-driven) → no app-boot test pinning needed.
