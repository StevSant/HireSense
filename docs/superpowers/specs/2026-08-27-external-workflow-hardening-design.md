# External workflow hardening design

## Goal

Make HireSense's application and ingestion workflows auditable, approval-gated,
reproducible, and safe to operate with untrusted job and email content.

## Decisions

- The database remains the system of record; generated files are addressed by
  content hash and never silently overwrite an approved packet.
- Existing candidate claims, job snapshots, application artifacts, source health,
  and inbox signals are extended rather than duplicated.
- External side effects remain explicitly user-approved. Ingestion and LLM
  content are data, never executable instructions.
- Quality checks are deterministic and degrade with a visible report when an
  optional system tool is unavailable.
- All new persistence is tenant-safe through the existing tracked-application
  ownership boundary and is covered by SQLite-compatible unit/integration tests.

## Scope

1. Versioned application packets with claim/artifact provenance and approval.
2. Deterministic CV/cover-letter quality reports and packet readiness endpoints.
3. Source fetch metadata, strict adapter result validation, and health reporting.
4. Outcome calibration and approval-backed inbox proposals.
5. Export/restore/doctor operations and reproducible dependency/CI checks.

## Non-goals

- Automatic submission to job portals.
- Live portal smoke tests that violate source terms or depend on unstable public HTML.
- Replacing the existing database, event bus, or matching pipeline.
