---
hide:
  - navigation
---

<div align="center" markdown>

![HireSense](assets/logo.svg){ width="320" }

### AI-assisted job hunting — ingest, rank, and apply, end to end.

</div>

HireSense pulls postings from job boards and company ATS portals, ranks them against your
profile with **pgvector semantic search + tiered LLM scoring**, and manages the whole
pipeline: tracking, CV & cover-letter generation, interview prep, outreach, and analytics.

![Discover view](assets/discover.png)

## How it works

1. **Ingest** — adapters pull postings from job boards and company ATS portals; jobs are
   upserted by stable identity and closed automatically when they disappear from the source.
2. **Rank** — a pgvector ANN pre-rank narrows the field, then skill overlap and tiered LLM
   scoring produce an explainable match score per role.
3. **Apply** — track applications end to end: generate tailored CVs and cover letters, prep
   for interviews, run outreach, and review analytics.

## Quick start

```bash
git clone https://github.com/StevSant/HireSense.git
cd HireSense
docker compose up --build   # db :5432 · app :8000 · frontend :4200 · Grafana :3000
```

See the [README](https://github.com/StevSant/HireSense#readme) for the full setup, and
[`backend/ARCHITECTURE.md`](https://github.com/StevSant/HireSense/blob/main/backend/ARCHITECTURE.md)
for the hexagonal, bounded-context backend design.

## Contributing

Issues and PRs are welcome. Start from the
[issue templates](https://github.com/StevSant/HireSense/issues/new/choose) and follow the
Conventional Commits convention (`type(scope): description`).
