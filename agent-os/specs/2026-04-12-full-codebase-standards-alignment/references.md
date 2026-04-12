# References for Full Codebase Standards Alignment

## Standards (Target State)

### Backend Standards

- **Location:** `agent-os/standards/backend/`
- `module-structure.md` — 4-layer module layout
- `dependency-injection.md` — Provider classes + app.state
- `domain-events.md` — Typed event fields, EventBus pattern
- `kernel-and-shared-types.md` — kernel/schemas/, kernel/events/, hiresense/ports/
- `llm-scorer.md` — BaseLLMScorer with _output_schema

### Frontend Standards

- **Location:** `agent-os/standards/frontend/`
- `domain-services.md` — One service per backend domain
- `models.md` — Domain-specific models in pages/{domain}/models/
- `signals-state.md` — Angular signals for reactive state
- `standalone-components.md` — Standalone components, lazy routes

## Existing Implementations (Reference Patterns)

### Ingestion Module (Best Backend Example)

- **Location:** `backend/src/hiresense/ingestion/`
- **Relevance:** Most complete module — has all 4 layers including ports/
- **Key patterns:** Adapter pattern for multiple job sources, normalizer layer, port definitions

### AuthService (Only Frontend Service)

- **Location:** `frontend/src/app/core/services/auth.service.ts`
- **Relevance:** The only existing domain service — pattern to replicate for other domains
- **Key patterns:** `@Injectable({ providedIn: 'root' })`, wraps HTTP calls
