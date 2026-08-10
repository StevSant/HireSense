# HireSense backend architecture

HireSense follows **hexagonal (ports & adapters) / clean architecture**. The codebase is split into
**bounded-context modules** under `src/hiresense/<module>/`, each layered the same way, plus a set of
**global ports/adapters** for cross-cutting infrastructure and a **composition layer** that wires
everything together.

The top level separates those three things by *kind*, so a business context is never mixed in
alphabetically with a technical layer:

```
src/hiresense/
├── main.py            # create_app()
├── shared/            # technical layers every context may use
│   ├── kernel/        #   shared primitives
│   ├── ports/         #   global Protocols
│   ├── adapters/      #   their implementations
│   ├── infrastructure/#   engine, session factory, ORM registry
│   ├── observability/ #   OpenTelemetry wiring
│   └── config/        #   Settings
├── composition/       # build_<module>() wiring — the only place a concrete impl is chosen
└── <bounded contexts> # ingestion, matching, applications, tracking, profile, …
```

## The dependency rule

Dependencies always point **inward**: `api → domain ← infrastructure`, and the domain depends only
on **ports** (abstract `Protocol`s), never on concrete adapters.

```mermaid
flowchart TB
    client(["HTTP client"])

    api["<b>api/</b><br/>FastAPI routes · request/response schemas<br/>Depends(...) providers"]
    domain["<b>domain/</b><br/>pure business logic + Pydantic models<br/><i>no sqlalchemy · no langchain · no httpx</i>"]
    ports["<b>ports/</b><br/>Protocols the domain is typed against"]
    infra["<b>infrastructure/</b><br/>SQLAlchemy *Orm · repositories · adapters<br/><i>knows frameworks &amp; the outside world</i>"]

    outside[("PostgreSQL 16 + pgvector<br/>HTTP job sources · LLM provider")]
    composition["<b>composition/</b><br/>composition layer — the only place<br/>a concrete implementation is chosen"]

    client --> api
    api -->|calls| domain
    domain -->|typed against| ports
    infra -->|implements| ports
    infra --> outside
    composition -.->|injects adapters into services| domain

    classDef pure fill:#0f766e22,stroke:#0f766e,stroke-width:2px
    classDef edge fill:#64748b22,stroke:#64748b
    class domain,ports pure
    class api,infra,composition edge
```

Read the arrows as *"depends on"*: everything points **inward**, toward `domain/`. `domain/`
itself points at nothing but its own ports — which is exactly what makes it testable without a
database, a network, or an LLM.

**Hard rules**
- `domain/` imports **nothing** from `infrastructure/` and pulls in **no** framework packages
  (`sqlalchemy`, `langchain*`, `httpx`, …). It may import ports and other domain code.
- Concrete classes (adapters, repositories) live in `infrastructure/` (or the global
  `shared/adapters/`) and each **implements a port**.
- Wiring (which concrete implementation is used) happens only in the **composition layer**
  (`composition/`), never via fallback imports inside the domain.

## The bounded contexts

Every module under `src/hiresense/` in the list below is a bounded context and follows the
layout in the next section. **Owns tables?** means the module declares its own `*Orm` classes
(registered in `shared/infrastructure/registry.py`) and maps them back to domain models in a
repository; *no* means it is stateless in the sense defined further down — it may still have a
read-only query adapter. Persistent modules declare the repository `Protocol` in a top-level
`ports/` package; `autopilot`, `inbox`, and `scheduler` instead keep theirs in
`domain/ports.py`. Both satisfy the dependency rule — the service is still typed against a
`Protocol`, never a concrete repository — but new modules should prefer the `ports/` package
form for consistency.

| Module | Responsibility | Owns tables? |
|---|---|:--:|
| `admin` | Runtime LLM configuration, per-feature overrides, usage/audit logging | yes |
| `analytics` | Market pay bands, best-fit companies/roles, pipeline conversion | no — read-only adapter over `ingestion` |
| `applications` | Per-application artifacts: match snapshot, tailored CV, cover letter, interview prep | yes |
| `autohunt` | One scheduled hunt run: new-since jobs → taste-rank → floor → top-N → a persisted `Digest` | yes |
| `autopilot` | End-to-end pipeline that turns hunt results into gated drafts awaiting approval | yes |
| `claims` | Candidate claims and the evidence backing them | yes |
| `cover_letter_templates` | Reusable opening/body/signature presets | yes |
| `identity` | Authentication: login, password hashing, JWT issue/verify | no |
| `inbox` | Inbound email → classified signals matched back onto tracked applications | yes |
| `ingestion` | Fetching, normalizing, deduplicating, and closing job postings | yes |
| `interview` | STAR stories and interview preparation material | yes |
| `matching` | Scoring a job against the profile: ANN pre-rank, skill overlap, tiered LLM dimensions | no |
| `network` | Professional contacts imported from LinkedIn connection exports | yes |
| `notifications` | Renders and delivers digest / signal / failure emails | no |
| `opportunities` | Non-job opportunities — conferences, CFPs, grants, funded events | yes |
| `optimization` | CV rewriting and optimization against a specific posting | no |
| `outreach` | Recruiter / hiring-manager message generation, outreach events, follow-up cadence | yes |
| `portfolio` | External proof-of-work sources; profile enrichment, citation, engagement readback | yes |
| `preference` | Preference-learning loop: explicit + implicit feedback signals → taste model | yes |
| `profile` | The candidate profile that everything else is ranked against | yes |
| `research` | Cached company research used by applications and outreach | yes |
| `scheduler` | Opt-in in-process recurring jobs (`SCHEDULER_ENABLED`) with run history and toggles | yes |
| `tracking` | Application pipeline: Saved → Applied → Interviewing → Offer, plus status history | yes |

### How they connect

The core hunt path is a chain of direct service calls, not an event choreography. Contexts are
composed in `composition/`, so a downstream context receives an upstream service (or a port) by
injection rather than importing it:

```mermaid
flowchart LR
    subgraph ext["External"]
        boards["Job boards<br/>RSS · JSON · MCP"]
        portals["Company ATS portals<br/>portals.yml"]
    end

    ingestion["<b>ingestion</b><br/>upsert by identity · content hash<br/>closure detection"]
    vec[("vector_embeddings<br/>pgvector")]
    matching["<b>matching</b><br/>ANN pre-rank → skill overlap<br/>→ tiered LLM dimensions"]
    profile["<b>profile</b>"]
    preference["<b>preference</b><br/>taste model"]
    applications["<b>applications</b><br/>CV · cover letter · prep"]
    tracking["<b>tracking</b><br/>Saved → Applied → Offer"]
    analytics["<b>analytics</b>"]

    boards --> ingestion
    portals --> ingestion
    ingestion -->|JobEmbeddingIndexer| vec
    vec -->|VectorStorePort.search| matching
    ingestion --> matching
    profile --> matching
    matching --> applications
    applications --> tracking
    tracking -.->|tracking.status_changed event| preference
    preference -.->|re-ranks| matching
    ingestion -.->|read-only corpus adapter| analytics
    tracking --> analytics
```

Only one domain event currently has a subscriber: `tracking.status_changed`, which
`composition/preference.py` wires into the preference-learning loop. `jobs.ingested` and
`match.completed` are published on the same bus but nothing listens for them yet — treat them
as available extension points, not as load-bearing wiring.

The packages under `src/hiresense/shared/` are deliberately **not** bounded contexts and do not
follow the `api/domain/infrastructure` layout:

| Package | What it is |
|---|---|
| `shared/observability` | Cross-cutting OpenTelemetry wiring — tracer/meter setup, exporters, JSON log formatting, request-id context, and ASGI middleware. |
| `shared/kernel` | Shared primitives every context may use: typed exceptions + their handlers, domain-event plumbing, value objects, pagination, rate limiter, LRU cache, security headers, skill normalization, prompt boundaries. |
| `shared/ports` / `shared/adapters` | The global ports and their implementations — see [Global ports & adapters](#global-ports--adapters). |
| `shared/infrastructure` | The async engine, session factory, declarative `Base`, and the ORM `registry.py` Alembic autogenerate reads. |
| `shared/config` | The `Settings` object: per-concern `BaseSettings` groups composed into one flat surface. |

`shared/__init__.py` stays empty on purpose — importing `hiresense.shared.kernel` must not drag in
telemetry, config, and every adapter. Import from the sub-package, never from `shared` itself.

## Per-module layout

```
src/hiresense/<module>/
├── api/
│   ├── routes.py          # FastAPI router
│   ├── schemas.py         # request/response Pydantic models
│   ├── dependencies.py    # Depends(...) providers reading app.state.<module>_provider
│   └── provider.py        # holds the module's services for injection
├── domain/
│   ├── models.py          # pure Pydantic domain models (no ORM)
│   └── services.py        # business logic, typed against ports
├── ports/
│   └── repository.py      # Protocol(s) the infrastructure must satisfy
└── infrastructure/
    ├── orm.py             # SQLAlchemy *Orm classes (the only place tables are defined)
    └── repository.py      # implements the port; maps ORM ↔ domain models
```

A **stateless** module (no persistence, no external I/O — e.g. `matching`, `optimization`,
`identity`) has **no** `ports/` or `infrastructure/` package. Don't add empty placeholder packages;
add a port only when there is a real abstraction boundary to cross.

**Carve-out — read-only query adapters.** "Stateless" means the module owns no persisted state: it
defines **no `*Orm` classes and never writes**. Such a module *may* still have an `infrastructure/`
package when it needs to **read** another module's corpus — a read-only aggregator that runs queries
against ORM models *owned by another module* and returns plain Python/Pydantic results. This is an
adapter (a real I/O boundary), not the module's own persistence, so it lives in `infrastructure/`
and is wired through `composition/` like any other adapter. Reference implementation:
`analytics/infrastructure/corpus_repository.py` (`CorpusAnalyticsRepository`) — a read-only
aggregator over `ingestion`'s `IngestedJob` (`status='open'`) that owns no tables of its own. The
rule of thumb: **owning an `*Orm` ⇒ persistent module (gets `ports/` + ORM + a mapping repository);
only reading someone else's ⇒ stateless module with a read-only query adapter.**

### The domain ↔ ORM mapping pattern

The domain model is pure Pydantic; the ORM lives in `infrastructure/orm.py` with an `Orm` suffix and
the same table/columns; the repository maps between them and returns **domain** models. Reference
implementation: `interview/` (`domain/models.py` `Story`, `infrastructure/orm.py` `StoryOrm`,
`infrastructure/repository.py` `_to_domain()`). `research/` and `cover_letter_templates/` follow the
same shape.

## Global ports & adapters

Cross-cutting infrastructure that any module may depend on:

| Port (`src/hiresense/shared/ports/`) | Adapter(s) | Location |
|---|---|---|
| `EmailSenderPort` | `SmtpEmailSender` (config-gated; raises `EmailUnavailableError` when SMTP is unset) | `shared/adapters/smtp_email_sender.py` |
| `EmbeddingPort` | `SentenceTransformerAdapter` | `shared/adapters/embedding/` |
| `EventBus` | `InMemoryEventBus` | `shared/adapters/event_bus/` |
| `LatexCompilerPort` | `LatexCompiler` | `shared/adapters/latex/` |
| `LLMPort` | `LangChainLLMAdapter` (base), `UsageTrackingLLMAdapter` (decorator) | `shared/adapters/llm/`, `admin/infrastructure/` |
| `MeteredLLMPort` | `LangChainLLMAdapter`, `FeatureConfiguredLLMAdapter` | `shared/adapters/llm/`, `admin/infrastructure/` |
| `VectorStorePort` | `PgVectorStore` | `shared/adapters/vector_store/` |

Module-level ports:

| Port | Adapter(s) | Module |
|---|---|---|
| `JobSourcePort` | `RemotiveAdapter`, `JobicyAdapter`, `GreenhouseAdapter`, … — **30 concrete adapters** re-exported from `ingestion.adapters` (boards, ATS portals, structured/CSV imports, and the `auto`/`scraper` fallbacks) | `ingestion/adapters/` |
| `JobsRepositoryPort` | `JobsRepository` (SQLAlchemy), `InMemoryJobsRepository` (tests) | `ingestion/infrastructure/` |
| `*RepositoryPort` | SQLAlchemy repository per module | `admin`, `applications`, `autohunt`, `claims`, `cover_letter_templates`, `interview`, `network`, `opportunities`, `outreach`, `portfolio`, `preference`, `profile`, `research`, `tracking` |

Two contexts ship their own outbound adapters beside their repositories:
`opportunities/adapters/` (`confs.tech` feed, curated import) and `portfolio/adapters/`
(GitHub, Supabase portfolio + engagement readback).

### LLM adapter chain (decorator pattern)

Usage tracking is a decorator over a config-resolving adapter over the raw LangChain adapter:

```
domain service ─uses→ LLMPort
   UsageTrackingLLMAdapter   (records tokens/cost/latency)          [admin/infrastructure]
     └─ wraps MeteredLLMPort
        FeatureConfiguredLLMAdapter   (resolves per-feature config, hot-reload)  [admin/infrastructure]
          └─ delegates to
             LangChainLLMAdapter   (the actual LangChain ainvoke/astream)         [shared/adapters/llm]
```

`MeteredLLMPort.generate()` returns an `LLMResult` (content + provider/model + token counts) so the
tracking decorator can record usage without changing the public `LLMPort.complete() -> str`.

## Composition layer (`composition/`)

Each module exposes a `build_<module>(infra, ...)` function that instantiates its repositories,
adapters, and services and returns a `Provider`. `main.py:create_app()` calls these builders in
dependency order and stores each `Provider` on `app.state`. FastAPI `Depends(...)` providers in
`<module>/api/dependencies.py` read the provider back off `app.state` per request.

`composition/shared_infra.py` builds the cross-cutting `SharedInfra` (settings, http client, event bus,
DB session factory, embedding, vector store) that every builder receives.

## Persistence & migrations

- SQLAlchemy 2.0, PostgreSQL. Repositories use the **sync** session factory
  (`infra.sync_session_factory`).
- Every ORM class must be imported in `shared/infrastructure/registry.py` so Alembic `--autogenerate` sees
  all tables.
- Semantic search uses **pgvector**: job embeddings are stored in an `embedding vector(N)` column and
  queried via `VectorStorePort`. Vector dimension is configured by `embedding_dim` in `shared/config/`.
- **ANN validation (opt-in):** the default suite runs against in-memory SQLite, which has no pgvector,
  so the `<=>` cosine ranking and eviction behaviour of `PgVectorStore` can only be validated against a
  real DB. `tests/integration/test_pgvector_ann.py` covers this and is marked `@pytest.mark.pgvector`.
  It is **skipped by default** (a conftest hook in `tests/integration/conftest.py` skips any
  `pgvector`-marked test unless the run is launched with `-m pgvector`; even then it skips gracefully if
  the DB is unreachable). To run it: `docker compose up db`, point `DATABASE_URL` at the compose DB
  (`postgresql+asyncpg://hiresense:hiresense@localhost:5432/hiresense`), then
  `uv run python -m pytest -m pgvector`. The fixture creates/cleans/drops the `vector_embeddings` table
  itself, so it is self-contained.

## Adding a new module — recipe

1. Create `src/hiresense/<module>/` with `api/`, `domain/`. Add `ports/` + `infrastructure/` only if
   the module persists data or talks to an external service.
2. Define the domain model as **pure Pydantic** in `domain/models.py` and the business logic in
   `domain/services.py`, typed against ports.
3. If persistent: define `infrastructure/orm.py` (`*Orm`), `ports/repository.py` (`Protocol`), and
   `infrastructure/repository.py` (maps ORM↔domain). Register the ORM in
   `shared/infrastructure/registry.py` and add an Alembic migration.
4. Add `api/provider.py`, `api/dependencies.py`, `api/routes.py`.
5. Add `composition/<module>.py` with `build_<module>(...)` and wire it in `main.py:create_app()`.
6. Keep every `__init__.py` re-exporting the package's public symbols (import from the contextual
   package, not the implementation file).

## Scaling constraints

The app runs as **exactly one uvicorn worker**. Several pieces of shared state live in process memory
and are not safe to duplicate across workers or replicas without externalizing them first:

- **Event bus:** `InMemoryEventBus` (`shared/adapters/event_bus/`) dispatches domain events in-process; a
  second worker would never see events published by the first.
- **Rate limiter:** `shared/kernel/rate_limit.py` tracks request counts in-process; a second worker resets
  the limiter's view of traffic, defeating the limit.
- **Scheduler:** the `scheduler` module's recurring jobs (autopilot pipeline, revalidation, etc.) run
  in-process; running them on multiple workers would duplicate every scheduled run.
- **Embedding model / LRU caches:** the `SentenceTransformerAdapter` and `shared/kernel/lru_cache.py`-backed
  caches are per-process — each additional worker reloads the model and starts with a cold cache.

Before adding workers (`--workers N`) or horizontally scaling the `app` service, externalize these:
move the event bus to a real broker, the rate limiter to Redis (or similar shared store), the
scheduler to a single leader-elected process (or an external cron calling the app's endpoints), and
accept the embedding model/cache being duplicated per process (or move to a shared inference
service). Until then, scale vertically (more CPU/memory per instance) rather than horizontally.

## Known follow-ups

- **Corpus-materialization pushdown:** ANN pre-ranking is wired end-to-end — job embeddings are
  persisted to the `vector_embeddings` table on ingestion (`JobEmbeddingIndexer`), and the job-list
  endpoint ranks via `SemanticPreRanker` (`ingestion/domain/semantic_pre_ranker.py`), which calls
  `PgVectorStore`/`VectorStorePort.search(...)` for ANN cosine ranking. The remaining work is pushing
  the rest of corpus materialization into SQL: filters and pagination currently applied in Python
  after the ANN query should move into the SQL query itself, and champions/min_score-exemption
  handling needs to operate over a bounded candidate window rather than the full corpus. Tracked by
  issue #132.
