# Full Codebase Standards Alignment — Shaping Notes

## Scope

Comprehensive refactor of both backend and frontend to align with the 9 architectural standards defined in `agent-os/standards/`. Covers folder/module structure, architecture patterns (DI, ports & adapters), and code quality (consistent patterns, proper abstractions). No behavior changes — purely structural.

## Decisions

- Single branch (`refactor/standards-alignment`) with one commit per task
- All 9 standards apply — no subset
- Backend and frontend both in scope
- Temporary re-export shims during transition to avoid breaking everything at once
- Identity module gets full 4-layer restructure despite being simple (consistency matters)
- Empty `agent/` directories cleaned up (not serving a purpose)
- Cross-domain models stay in `core/models/`; domain-specific models move to `pages/{domain}/models/`

## Context

- **Visuals:** None
- **References:** `agent-os/standards/` (the target state is defined by the standards themselves)
- **Product alignment:** N/A (no product docs exist yet)

## Standards Applied

- **backend/module-structure** — every module needs all 4 layers (api, domain, infrastructure, ports)
- **backend/dependency-injection** — Provider classes + app.state, no dependency_overrides
- **backend/domain-events** — typed event fields, no generic payload dict
- **backend/kernel-and-shared-types** — schemas/ and events/ under kernel, shared ports at top-level
- **backend/llm-scorer** — standardized BaseLLMScorer with _output_schema, typed LLMPort
- **frontend/domain-services** — one service per backend domain, components never inject HttpClient
- **frontend/models** — domain-specific in pages/{domain}/models/, shared in core/models/
- **frontend/signals-state** — signals for reactive state, computed for derived
- **frontend/standalone-components** — standalone: true, lazy routes, no NgModules
