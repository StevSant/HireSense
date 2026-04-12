# Models

Models are TypeScript `interface`s organized by domain, not centralized in `core/models/`.

## File Location

```
pages/
  tracking/
    models/
      tracked-application.model.ts
      application-status.model.ts
      create-application-request.model.ts
  ingestion/
    models/
      normalized-job.model.ts
      portal-entry.model.ts
  matching/
    models/
      evaluation-result.model.ts
      evaluate-request.model.ts
```

Shared models used across multiple domains stay in `core/models/`.

## Rules

- Use `interface`, not `class`, for data shapes
- One interface per file
- File naming: `{name}.model.ts`
- Domain-specific models live in `pages/{domain}/models/`
- Cross-domain models live in `core/models/`
- Export the interface as a named export
