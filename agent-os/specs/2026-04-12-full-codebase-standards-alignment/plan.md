# HireSense Full Codebase Standards Alignment

## Context

The HireSense codebase has well-defined architectural standards in `agent-os/standards/` but the implementation has drifted from them. Key problems: identity module breaks the 4-layer structure, all DI uses `dependency_overrides` instead of Provider classes, shared types are in `kernel/contracts/` instead of `kernel/schemas/` + `kernel/events/`, shared ports are in `kernel/ports/` instead of top-level `hiresense/ports/`, and the frontend has no domain services (components inject `HttpClient` directly). This refactor aligns everything with the 9 existing standards without changing behavior.

**Branch:** `refactor/standards-alignment` (single branch, one commit per task)

---

## Task 1: Save Spec Documentation

Create `agent-os/specs/2026-04-12-full-codebase-standards-alignment/` with:
- `plan.md` — This plan
- `shape.md` — Shaping notes from our conversation
- `standards.md` — All 9 standards that apply
- `references.md` — Pointers to standards files

---

## Task 2: Reorganize kernel/ (schemas + events)

Split `kernel/contracts/` into `kernel/schemas/` and `kernel/events/` per the kernel-and-shared-types standard.

**Create:**
- `backend/src/hiresense/kernel/schemas/__init__.py`
- `backend/src/hiresense/kernel/schemas/normalized_job_dto.py` (from `contracts/ingestion.py` — DTO part)
- `backend/src/hiresense/kernel/schemas/match_result_dto.py` (from `contracts/matching.py` — DTO part)
- `backend/src/hiresense/kernel/schemas/optimization_request_dto.py` (from `contracts/optimization.py`)
- `backend/src/hiresense/kernel/schemas/tex_diff_dto.py` (from `contracts/optimization.py`)
- `backend/src/hiresense/kernel/schemas/candidate_skills_dto.py` (from `contracts/profile.py`)
- `backend/src/hiresense/kernel/schemas/cv_embedding_dto.py` (from `contracts/profile.py`)
- `backend/src/hiresense/kernel/events/__init__.py`
- `backend/src/hiresense/kernel/events/base.py` (moved from `kernel/events.py`)
- `backend/src/hiresense/kernel/events/jobs_ingested.py` (from `contracts/ingestion.py` — event part + `contracts/jobs_ingested_event.py`)
- `backend/src/hiresense/kernel/events/match_completed.py` (from `contracts/matching.py` — event part)

**Update:** All imports across modules from `kernel.contracts` to `kernel.schemas`/`kernel.events`. Keep `kernel/contracts/` as re-export shims temporarily.

**Also:** Fix `DomainEvent` — remove `payload: dict[str, Any]` field. Update `JobsIngestedEvent` and `MatchCompletedEvent` to use typed fields instead. Update publishers in `ingestion/domain/services.py` and `matching/domain/services.py`.

**Verify:** `uv run pytest tests/unit/ -x`

---

## Task 3: Relocate shared ports to hiresense/ports/

Move `kernel/ports/` contents to top-level `hiresense/ports/` per the kernel-and-shared-types standard.

**Create:**
- `backend/src/hiresense/ports/__init__.py`
- `backend/src/hiresense/ports/event_bus.py`
- `backend/src/hiresense/ports/llm.py`
- `backend/src/hiresense/ports/vector_store.py`
- `backend/src/hiresense/ports/latex_compiler.py`

**Update:** All imports from `kernel.ports` to `hiresense.ports`. Leave `kernel/ports/` as re-export shim temporarily.

**Verify:** `uv run pytest tests/unit/ -x`

---

## Task 4: Restructure identity module to 4-layer

The identity module has `services.py` at root level. Standard requires `api/`, `domain/`, `infrastructure/`, `ports/`.

**Create:**
- `backend/src/hiresense/identity/domain/__init__.py`
- `backend/src/hiresense/identity/domain/services.py` (move from `identity/services.py`)
- `backend/src/hiresense/identity/api/schemas.py` (extract `LoginRequest`, `TokenResponse` from routes.py)
- `backend/src/hiresense/identity/infrastructure/__init__.py`
- `backend/src/hiresense/identity/ports/__init__.py`

**Update:** `identity/__init__.py`, `identity/api/routes.py`, `identity/api/dependencies.py` — fix import paths.

**Delete:** `backend/src/hiresense/identity/services.py` (moved)

**Verify:** `uv run pytest tests/unit/identity/ -x`

---

## Task 5: Add ports/ layer to remaining modules

Standard requires `ports/` in every module. Currently only `ingestion/ports/` exists.

**Create for each (matching, optimization, profile, tracking, interview, research):**
- `{module}/ports/__init__.py`

**For modules with repository dependencies, extract Protocol interfaces:**
- `tracking/ports/repository.py` — `TrackingRepositoryPort`
- `interview/ports/repository.py` — `StoryRepositoryPort`
- `research/ports/repository.py` — `CompanyResearchRepositoryPort`

**Update:** Type hints in `tracking/domain/services.py`, `interview/domain/services.py`, `research/domain/services.py` to use port Protocols instead of concrete types.

**Verify:** `uv run pytest tests/unit/ -x`

---

## Task 6: Create Provider classes per module

Replace `dependency_overrides` pattern with Provider classes per the DI standard.

**Create `api/provider.py` for each module (8 files):**
- `identity/api/provider.py` — `IdentityProvider`
- `ingestion/api/provider.py` — `IngestionProvider`
- `matching/api/provider.py` — `MatchingProvider`
- `optimization/api/provider.py` — `OptimizationProvider`
- `profile/api/provider.py` — `ProfileProvider`
- `tracking/api/provider.py` — `TrackingProvider`
- `interview/api/provider.py` — `InterviewProvider`
- `research/api/provider.py` — `ResearchProvider`

**Update all `{module}/api/dependencies.py`:**
- Add `request: Request` parameter
- Read from `request.app.state.{module}.get_*()` instead of raising `NotImplementedError`
- Extract any inline dependencies from `routes.py` to `dependencies.py` (e.g., ingestion module)

**Verify:** `uv run pytest tests/unit/ -x` — tests using `dependency_overrides` will need updating to use Provider with test doubles.

---

## Task 7: Refactor main.py to use Providers + app.state

Replace all `dependency_overrides` in `main.py` with Provider instantiation stored on `app.state`.

**Modify:** `backend/src/hiresense/main.py`
- Build Providers: `app.state.identity = IdentityProvider(...)`, etc.
- Remove all `app.dependency_overrides[...]` lines
- Remove backward-compatibility re-export shims in `kernel/contracts/` and `kernel/ports/`

**Delete (cleanup from Tasks 2-3):**
- `backend/src/hiresense/kernel/events.py`
- `backend/src/hiresense/kernel/contracts/` directory (all consumers now use `kernel/schemas/` and `kernel/events/`)
- `backend/src/hiresense/kernel/ports/` directory (all consumers now use `hiresense/ports/`)

**Verify:** `uv run pytest tests/unit/ -x`, especially `test_app.py`

---

## Task 8: Align LLM scorers with llm-scorer standard

**Modify:** `backend/src/hiresense/matching/domain/scorers/llm_scorer.py`
- Type `llm` parameter as `LLMPort | None` (from `hiresense.ports`)
- Remove `_build_system()` abstract method; add standardized system prompt in base
- Add `_output_schema()` abstract method returning `type[BaseModel]`
- Simplify response parsing

**Modify all 6 scorer subclasses:**
- `seniority_scorer.py`, `compensation_scorer.py`, `growth_scorer.py`, `culture_scorer.py`, `application_strength_scorer.py`, `interview_readiness_scorer.py`
- Remove `_build_system()`, add `_output_schema()`

**Verify:** `uv run pytest tests/unit/matching/ -x`

---

## Task 9: Cleanup empty agent/ directories

**Delete:**
- `backend/src/hiresense/matching/agent/` (empty, only `__init__.py`)
- `backend/src/hiresense/optimization/agent/` (empty, only `__init__.py`)

**Verify:** `uv run pytest tests/unit/ -x`

---

## Task 10: Relocate frontend models to pages/{domain}/models/

Per the models standard, domain-specific models move to `pages/{domain}/models/`.

**Move from `core/models/` to domain-specific locations:**
- `evaluate-request.model.ts`, `evaluation-result.model.ts` -> `pages/matching/models/`
- `batch-evaluation-response.model.ts`, `batch-result.model.ts`, `tracked-application.model.ts`, `update-application-request.model.ts`, `company-research.model.ts` -> `pages/tracking/models/`
- `normalized-job.model.ts`, `portal-entry.model.ts`, `scan-portals-request.model.ts`, `scan-result.model.ts` -> `pages/ingestion/models/`
- `competency.model.ts`, `story.model.ts`, `story-match.model.ts`, `interview-prep.model.ts` -> `pages/interview/models/`

**Extract inline interfaces to model files:**
- `MatchingComponent` -> `pages/matching/models/score-breakdown.model.ts`, `match-result.model.ts`
- `OptimizationComponent` -> `pages/optimization/models/section-change.model.ts`, `optimization-result.model.ts`
- `ProfileComponent` -> `pages/profile/models/cv-section.model.ts`, `candidate-profile.model.ts`
- `IngestionComponent` -> `pages/ingestion/models/fetch-response.model.ts`

**Keep in `core/models/` (cross-domain):**
- `application-status.model.ts`
- `dimension-result.model.ts`
- `create-application-request.model.ts`

**Update all imports in components.**

**Verify:** `ng build`

---

## Task 11: Create frontend domain services

Per the domain-services standard, create one service per backend domain.

**Create (7 files in `frontend/src/app/core/services/`):**
- `ingestion.service.ts` — wraps `/ingestion/fetch`, `/ingestion/scan-portals`, `/ingestion/portals`
- `matching.service.ts` — wraps `/matching/evaluate`, `/matching/analyze`, `/matching/batch-evaluate`
- `tracking.service.ts` — wraps `/tracking` CRUD endpoints
- `profile.service.ts` — wraps `/profile/upload`
- `optimization.service.ts` — wraps `/optimization/optimize`
- `interview.service.ts` — wraps `/interview/stories` CRUD, `/interview/prepare`
- `research.service.ts` — wraps `/research`, `/research/refresh`

All services: `@Injectable({ providedIn: 'root' })`, inject `HttpClient`, return `Observable<T>`.

**Verify:** `ng build`

---

## Task 12: Refactor components to use domain services

Replace direct `HttpClient` usage in all page components with domain service injection.

**Modify (6 component files):**
- `pages/ingestion/ingestion.component.ts` — inject `IngestionService`, `TrackingService`
- `pages/matching/matching.component.ts` — inject `MatchingService`
- `pages/tracking/tracking.component.ts` — inject `TrackingService`, `MatchingService`, `ResearchService`
- `pages/profile/profile.component.ts` — inject `ProfileService`
- `pages/optimization/optimization.component.ts` — inject `OptimizationService`
- `pages/interview/interview.component.ts` — inject `InterviewService`

Remove `HttpClient` imports from components.

**Verify:** `ng build`, then manual testing of each page in browser.

---

## Execution Order

```
Phase 1 (parallel): Task 1 (spec docs), Task 2 (kernel reorg), Task 10 (frontend models)
Phase 2 (parallel): Task 3 (shared ports), Task 11 (frontend services)
Phase 3 (parallel): Task 4 (identity 4-layer), Task 12 (frontend components)
Phase 4: Task 5 (module ports)
Phase 5: Task 6 (provider classes)
Phase 6: Task 7 (main.py refactor + cleanup)
Phase 7: Task 8 (LLM scorers)
Phase 8: Task 9 (cleanup agent/ dirs)
```

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Circular imports during kernel reorg | High | Use `from __future__ import annotations`, keep import direction api->domain->ports |
| Test breakage from DI refactor | High | Update tests in same commit as provider change |
| Frontend import path breakage | Medium | Run `ng build` after each model move |
| Event payload removal breaks tests | Medium | Grep for `.payload` in tests before Task 2 |
| LLM scorer structured output needs adapter change | Low | Assess adapter capabilities before Task 8 |

## Verification

After all tasks complete:
1. `uv run pytest tests/unit/ -x` — all backend tests pass
2. `ng build` — frontend compiles
3. `docker-compose up` — full stack starts
4. Manual testing of each page: ingestion, matching, tracking, profile, optimization, interview
5. Verify no `dependency_overrides` in production code
6. Verify no imports from `kernel/contracts/` or `kernel/ports/`
7. Verify all page components inject domain services, not `HttpClient`
