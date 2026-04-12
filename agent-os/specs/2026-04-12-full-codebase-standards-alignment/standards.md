# Standards for Full Codebase Standards Alignment

The following 9 standards apply to this work. See each file for full content.

## Backend Standards

- `agent-os/standards/backend/module-structure.md` — 4-layer layout (api, domain, infrastructure, ports) required for every module
- `agent-os/standards/backend/dependency-injection.md` — Provider classes + app.state, no dependency_overrides
- `agent-os/standards/backend/domain-events.md` — Typed DomainEvent fields, events in kernel/events/, dotted naming
- `agent-os/standards/backend/kernel-and-shared-types.md` — kernel/schemas/ for DTOs, kernel/events/ for events, hiresense/ports/ for shared protocols
- `agent-os/standards/backend/llm-scorer.md` — BaseLLMScorer with LLMPort, _output_schema(), no _build_system()

## Frontend Standards

- `agent-os/standards/frontend/domain-services.md` — One service per backend domain, components never inject HttpClient
- `agent-os/standards/frontend/models.md` — Domain models in pages/{domain}/models/, shared in core/models/
- `agent-os/standards/frontend/signals-state.md` — signal() for state, computed() for derived, no BehaviorSubject
- `agent-os/standards/frontend/standalone-components.md` — standalone: true, loadComponent(), no NgModules
