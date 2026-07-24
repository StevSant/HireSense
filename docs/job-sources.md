# Job sources — operator guide

HireSense ingests board sources declared in `ENABLED_JOB_SOURCES` and company ATS
portals from `portals.yml`. Capability metadata is available at
`GET /ingestion/sources`; per-source run health at `GET /ingestion/sources/health`.

## Automated sources (no credentials)

| Source | Method | Closure | Notes |
|---|---|---|---|
| `dice` | Official MCP `search_jobs` | URL probe | Configure `DICE_QUERY`, remote/page limits |
| `crunchboard` | Official `jobs.rss` | URL probe | Latest-window feed |
| `yc_jobs` | Public Work at a Startup Inertia JSON | URL probe | Role list via `YC_JOBS_ROLES`; optional company enrich |
| Existing boards | API / RSS / HTML | see capabilities | Remotive, RemoteOK, Jobicy, … |

## Import fallbacks (opt-in)

Indeed, Wellfound, Glassdoor, and Monster have **no legitimate public job-search API**
suitable for HireSense (APIs shut down or invite-only; HTML is bot-walled). Enable the
source name in `ENABLED_JOB_SOURCES` and place a JSONL/CSV file under `CSV_IMPORT_DIR`:

| Source | Default filename |
|---|---|
| `indeed` | `indeed_jobs.jsonl` |
| `wellfound` | `wellfound_jobs.jsonl` |
| `glassdoor` | `glassdoor_jobs.jsonl` |
| `monster` | `monster_jobs.jsonl` |

Minimal JSONL record:

```json
{"id":"abc","title":"Engineer","company":"Acme","url":"https://example.com/jobs/abc","location":"Remote","remote":true,"salary_range":"$140k-$160k","description":"..."}
```

Wellfound may also include `equity_range`, `company_stage`, `team_size`, `funding`,
`visa_sponsorship_available`, `skills`. Glassdoor may include `company_rating`,
`company_size`, `industry`, `headquarters` — **never** review bodies.

Missing files yield an empty fetch (not an error). Path traversal outside the import
dir is rejected.

## Adding another source

1. Implement `JobSourcePort` in `ingestion/adapters/`.
2. Add a normalizer returning `NormalizedJob` field dicts (including optional
   `employment_type`, `equity_range`, `source_metadata`).
3. Register capabilities in `source_capabilities.py`.
4. Wire config + bootstrap branch; export from package `__init__.py`.
5. Unit-test with FakeHttp / fixtures (no live network in default CI).
6. Document knobs in `.env.example`.

## Optional live smoke tests

Marked tests that hit third-party networks must use `@pytest.mark.live_sources` and
remain skipped by default. Do not bypass Cloudflare/DataDome/login walls.

## Troubleshooting

| Symptom | Check |
|---|---|
| Source missing from filters | `GET /ingestion/sources` — is it `enabled` and `wired`? |
| Dice empty | `DICE_QUERY` too narrow; MCP endpoint reachable? |
| YC empty | Accept HTML headers / Inertia `data-page` shape changed? |
| Import empty | File present under `CSV_IMPORT_DIR` with required title+company? |
| Source health `failing` | `GET /ingestion/sources/health` → `last_error` |
