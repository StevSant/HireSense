# HireSense backend architecture

HireSense follows **hexagonal (ports & adapters) / clean architecture**. The codebase is split into
**bounded-context modules** under `src/hiresense/<module>/`, each layered the same way, plus a set of
**global ports/adapters** for cross-cutting infrastructure and a **composition layer** that wires
everything together.

## The dependency rule

Dependencies always point **inward**: `api → domain ← infrastructure`, and the domain depends only
on **ports** (abstract `Protocol`s), never on concrete adapters.

```
        ┌──────────────────────────────────────────────┐
        │                    api/                       │  HTTP routes, request/response schemas,
        │   (FastAPI routes, schemas, dependencies)     │  FastAPI dependency providers
        └───────────────────┬──────────────────────────┘
                            │ calls
        ┌───────────────────▼──────────────────────────┐
        │                  domain/                      │  pure business logic + Pydantic models.
        │   services, domain models, ports (Protocols)  │  NO sqlalchemy, NO langchain, NO httpx.
        └───────────────────▲──────────────────────────┘
                            │ implements (depends inward)
        ┌───────────────────┴──────────────────────────┐
        │              infrastructure/                  │  repositories, ORM classes, adapters.
        │   (SQLAlchemy ORM, adapters, persistence)     │  Knows about frameworks & the outside world.
        └──────────────────────────────────────────────┘
```

**Hard rules**
- `domain/` imports **nothing** from `infrastructure/` and pulls in **no** framework packages
  (`sqlalchemy`, `langchain*`, `httpx`, …). It may import ports and other domain code.
- Concrete classes (adapters, repositories) live in `infrastructure/` (or the global `adapters/`)
  and each **implements a port**.
- Wiring (which concrete implementation is used) happens only in the **composition layer**
  (`bootstrap/`), never via fallback imports inside the domain.

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
and is wired through `bootstrap/` like any other adapter. Reference implementation:
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

| Port (`src/hiresense/ports/`) | Adapter(s) | Location |
|---|---|---|
| `EmbeddingPort` | `SentenceTransformerAdapter` | `adapters/embedding/` |
| `EventBus` | `InMemoryEventBus` | `adapters/event_bus/` |
| `LatexCompilerPort` | `LatexCompiler` | `adapters/latex/` |
| `LLMPort` | `LangChainLLMAdapter` (base), `UsageTrackingLLMAdapter` (decorator) | `adapters/llm/`, `admin/infrastructure/` |
| `MeteredLLMPort` | `LangChainLLMAdapter`, `FeatureConfiguredLLMAdapter` | `adapters/llm/`, `admin/infrastructure/` |
| `VectorStorePort` | `PgVectorStore` | `adapters/vector_store/` |

Module-level ports:

| Port | Adapter(s) | Module |
|---|---|---|
| `JobSourcePort` | `RemotiveAdapter`, `JobicyAdapter`, `GreenhouseAdapter`, … (12 sources) | `ingestion/adapters/` |
| `JobsRepositoryPort` | `JobsRepository` (SQLAlchemy), `InMemoryJobsRepository` (tests) | `ingestion/infrastructure/` |
| `*RepositoryPort` | SQLAlchemy repository per module | `applications`, `profile`, `tracking`, `interview`, `research`, `cover_letter_templates`, `admin` |

### LLM adapter chain (decorator pattern)

Usage tracking is a decorator over a config-resolving adapter over the raw LangChain adapter:

```
domain service ─uses→ LLMPort
   UsageTrackingLLMAdapter   (records tokens/cost/latency)          [admin/infrastructure]
     └─ wraps MeteredLLMPort
        FeatureConfiguredLLMAdapter   (resolves per-feature config, hot-reload)  [admin/infrastructure]
          └─ delegates to
             LangChainLLMAdapter   (the actual LangChain ainvoke/astream)         [adapters/llm]
```

`MeteredLLMPort.generate()` returns an `LLMResult` (content + provider/model + token counts) so the
tracking decorator can record usage without changing the public `LLMPort.complete() -> str`.

## Composition layer (`bootstrap/`)

Each module exposes a `build_<module>(infra, ...)` function that instantiates its repositories,
adapters, and services and returns a `Provider`. `main.py:create_app()` calls these builders in
dependency order and stores each `Provider` on `app.state`. FastAPI `Depends(...)` providers in
`<module>/api/dependencies.py` read the provider back off `app.state` per request.

`bootstrap/shared_infra.py` builds the cross-cutting `SharedInfra` (settings, http client, event bus,
DB session factory, embedding, vector store) that every builder receives.

## Persistence & migrations

- SQLAlchemy 2.0, PostgreSQL. Repositories use the **sync** session factory
  (`infra.sync_session_factory`).
- Every ORM class must be imported in `infrastructure/registry.py` so Alembic `--autogenerate` sees
  all tables.
- Semantic search uses **pgvector**: job embeddings are stored in an `embedding vector(N)` column and
  queried via `VectorStorePort`. Vector dimension is configured by `embedding_dim` in `config.py`.

## Adding a new module — recipe

1. Create `src/hiresense/<module>/` with `api/`, `domain/`. Add `ports/` + `infrastructure/` only if
   the module persists data or talks to an external service.
2. Define the domain model as **pure Pydantic** in `domain/models.py` and the business logic in
   `domain/services.py`, typed against ports.
3. If persistent: define `infrastructure/orm.py` (`*Orm`), `ports/repository.py` (`Protocol`), and
   `infrastructure/repository.py` (maps ORM↔domain). Register the ORM in
   `infrastructure/registry.py` and add an Alembic migration.
4. Add `api/provider.py`, `api/dependencies.py`, `api/routes.py`.
5. Add `bootstrap/<module>.py` with `build_<module>(...)` and wire it in `main.py:create_app()`.
6. Keep every `__init__.py` re-exporting the package's public symbols (import from the contextual
   package, not the implementation file).

## Known follow-ups

- **pgvector search swap:** job embeddings are now persisted to the `vector_embeddings` table on
  ingestion (`JobEmbeddingIndexer`), and `PgVectorStore` implements ANN search. The job-list endpoint
  still ranks via the in-memory `SemanticScoringService`; swapping it to `vector_store.search(...)`
  is the remaining integration. It was left out here because it can't be validated without a live
  Postgres+pgvector instance — do it alongside that validation.
