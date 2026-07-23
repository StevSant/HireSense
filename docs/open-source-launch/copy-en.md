# English Publishing Copy

The copy is prefilled for **HireSense** and its public repository:

- Repository: <https://github.com/StevSant/HireSense>
- Live demo: <https://hiresense-demo.vercel.app>
- Architecture article: <https://github.com/StevSant/HireSense/blob/main/backend/ARCHITECTURE.md>

The live demo is frontend-only, read-only, and uses synthetic data. It requires no account
and is safe to share publicly.

Do not publish metrics or source counts without checking them immediately before posting.

## Core positioning

### Primary tagline

> Turn the job-board firehose into a private, ranked shortlist.

### One-sentence description

> HireSense is a self-hosted job-search workspace for candidates that ingests and
> deduplicates listings, ranks the whole corpus with pgvector and cost-aware LLM scoring,
> and manages applications end to end.

### GitHub About description

> Self-hosted job search for candidates: ingest and deduplicate listings, rank them with
> pgvector and LLMs, and manage applications end to end.

### Social-preview text

```text
HireSense
Private, ranked job search—end to end.
Open source · Self-hosted
```

## LinkedIn

### Primary launch post

> I got tired of managing a job search across five different tools, so I built one.
>
> Today I’m releasing **HireSense**, an open-source, self-hosted workspace for job
> seekers.
>
> It collects roles from public job boards and company ATS portals, removes duplicates, and
> ranks the complete job corpus against your profile using pgvector semantic search, skill
> matching, and cost-aware LLM scoring.
>
> From there, it helps manage the rest of the process: application tracking, tailored CVs
> and cover letters, interview preparation, outreach, and market analytics.
>
> I made it self-hosted because a CV, salary expectations, job preferences, and application
> history are deeply personal data.
>
> The stack includes Python, FastAPI, Angular, PostgreSQL/pgvector, Docker, LangChain,
> OpenTelemetry, and Grafana.
>
> This is the first public preview. I would especially value feedback on the installation
> experience and the ranking approach.
>
> Live demo (read-only, synthetic data): https://hiresense-demo.vercel.app
>
> Repository: https://github.com/StevSant/HireSense
>
> If it is useful, consider starring it or contributing to one of the beginner-friendly
> issues.
>
> #OpenSource #SelfHosted #Python #JobSearch

### Short follow-up post

> One design decision in HireSense matters more than the AI label: ranking happens
> across the full job corpus before pagination.
>
> Otherwise, an excellent match can remain buried on page 40 simply because only the
> current page was scored.
>
> The pipeline uses pgvector for semantic pre-ranking, skill overlap for a fast structured
> signal, and tiered LLM scoring only where the extra cost is justified.
>
> I wrote up the architecture and trade-offs here:
> https://github.com/StevSant/HireSense/blob/main/backend/ARCHITECTURE.md
>
> What would you optimize first: ranking quality, explainability, or cost?
>
> #PostgreSQL #pgvector #MachineLearning #OpenSource

### Suggested first comment

> A quick clarification: this is candidate-side software, not a recruiter screening tool.
> The goal is to help an individual turn a noisy set of listings into a manageable shortlist
> while keeping their profile and application history under their control.

## Reddit

Read each community's current rules and rewrite the draft in your own voice before posting.
Do not publish these in several communities at the same time.

### `r/selfhosted`

**Title**

> I built a self-hosted job-search workspace with pgvector ranking and an end-to-end application pipeline

**Body**

> I wanted a job-search workflow where my CV, preferences, salary expectations, and
> application history did not have to live in another SaaS product, so I built HireSense.
>
> It ingests roles from public job boards and company ATS portals, deduplicates them by stable
> identity, ranks the full corpus with pgvector plus skill and optional LLM scoring, and
> tracks applications through interview and offer stages. It also includes tailored document
> generation, interview preparation, scheduling, analytics, and OpenTelemetry/Grafana
> observability.
>
> The stack runs with Docker Compose: FastAPI, Angular, PostgreSQL/pgvector, and Grafana. A
> local heuristic mode is available for trying the workflow without a paid LLM provider.
>
> Repository: https://github.com/StevSant/HireSense
>
> I would value blunt feedback on the deployment experience, default resource footprint, and
> which external dependencies should remain optional. What would stop you from self-hosting
> something like this?

### `r/opensource`

**Title**

> HireSense: an MIT-licensed, candidate-side job-search and application workspace

**Body**

> I’m preparing the first public release of HireSense, a self-hosted job-search system
> built around FastAPI, Angular, PostgreSQL/pgvector, and a hexagonal backend architecture.
>
> The repository already includes an MIT license, security policy, contribution guide, Code
> of Conduct, issue forms, CI, and architecture documentation. The main contribution areas
> are source adapters, ranking quality, onboarding, accessibility, and documentation.
>
> Repository: https://github.com/StevSant/HireSense
>
> I am especially interested in feedback from maintainers: is the contribution path clear,
> and which small issue would make the best first external contribution?

### `r/SideProject`

**Title**

> I turned my fragmented job-search workflow into an open-source, self-hosted application

**Body**

> My job search kept expanding into separate spreadsheets, job-board tabs, CV copies,
> interview notes, and reminders. I started HireSense to put that workflow in one
> place.
>
> The most interesting engineering problem was not generating text. It was reducing the
> firehose: deduplicating jobs, ranking the complete corpus instead of one page, controlling
> LLM cost, and keeping listings current when sources change or disappear.
>
> It has grown into a FastAPI + Angular application with PostgreSQL/pgvector, Docker,
> application tracking, tailored artifacts, interview preparation, analytics, automation,
> and observability.
>
> Repository: https://github.com/StevSant/HireSense
>
> I would love feedback on whether the product story is understandable in the first minute.

## Product Hunt

Use Product Hunt only after the product is directly usable through a hosted demo or a very
smooth local trial.

### Tagline

> Turn the job-board firehose into a private, ranked shortlist

### Short description

> HireSense is an open-source, self-hosted workspace that finds and deduplicates job
> listings, ranks them against your profile, and supports the application process from
> tailored documents to interview preparation and analytics.

### Maker first comment

> Hi Product Hunt — I built HireSense after realizing that job hunting had become a
> collection of disconnected tools: job boards for discovery, spreadsheets for tracking,
> document copies for every application, separate interview notes, and no useful view of what
> was working.
>
> The core idea is to reduce noise before adding more automation. HireSense ingests
> roles from public boards and company ATS portals, deduplicates them, semantically pre-ranks
> the complete corpus with pgvector, and uses skill matching and optional tiered LLM scoring
> to build a shortlist.
>
> It then supports the workflow around that shortlist: tracking, tailored CVs and cover
> letters, interview preparation, outreach, automation, and market analytics.
>
> It is MIT-licensed and self-hosted because candidate data is personal. The public preview
> source code is available at https://github.com/StevSant/HireSense.
>
> I would value feedback on two things: whether the first-run experience is clear, and which
> part of the job-search workflow you would want to automate—or deliberately keep manual.

Do not ask anyone to upvote. Invite people to try it and comment.

## Show HN

Hacker News currently prohibits generated or AI-edited comments. Do not paste a generated
submission from this file. Write the final text personally after reading the current
[Show HN guidelines](https://news.ycombinator.com/showhn.html) and
[general guidelines](https://news.ycombinator.com/newsguidelines.html).

An honest title should use this structure:

```text
Show HN: HireSense – Self-hosted job search with pgvector and tiered LLM scoring
```

Write a short discussion in your own words covering:

1. The personal frustration that started the project.
2. What someone can try immediately and how.
3. Why whole-corpus ranking differs from scoring only a visible page.
4. How pgvector, skill signals, and tiered models balance quality and cost.
5. Why the project is self-hosted.
6. One limitation or unfinished area you genuinely want feedback on.

Avoid emoji, marketing adjectives, unsupported metrics, and requests for votes or comments.
Stay available to answer technical questions after submitting.

## DEV Community / Hashnode

### Recommended article

**Title**

> How I built a cost-aware job-ranking pipeline with pgvector and tiered LLM scoring

**Subtitle**

> Why ranking the whole corpus before pagination produced a better shortlist—and how cheap
> filters keep expensive model calls proportional to signal.

**Outline**

1. The page-ranking failure mode.
2. Stable identity and deduplication before scoring.
3. Whole-corpus pgvector ANN pre-ranking.
4. Skill-overlap signals.
5. Tiered LLM scoring and caching.
6. Explainability and null-score behavior.
7. Cost and quality measurements.
8. Failure cases and next experiments.
9. Repository and reproducible setup.

**Suggested DEV tags**

```text
#python #postgres #machinelearning #opensource
```

### Additional article titles

- Why my job-search app ranks the entire corpus before showing page one
- Designing a self-hosted AI application around candidate privacy
- Stable identity, content hashes, and the surprisingly hard problem of stale job listings
- Using hexagonal architecture in a FastAPI application with many external adapters
- Instrumenting LLM calls with OpenTelemetry, Tempo, Loki, and Grafana

## Short social copy

### X / Bluesky / Mastodon

> I built HireSense: an open-source, self-hosted job-search workspace that deduplicates
> listings, ranks the full corpus with pgvector + optional LLM scoring, and manages the
> application process end to end.
>
> Source: https://github.com/StevSant/HireSense
>
> Demo: https://hiresense-demo.vercel.app

### YouTube title

> I built a self-hosted job-search platform with FastAPI, Angular, and pgvector

### YouTube description

> HireSense turns job listings into a deduplicated, ranked shortlist, then supports
> application tracking, tailored documents, interview preparation, outreach, and analytics.
>
> Source code and documentation: https://github.com/StevSant/HireSense
>
> Live demo: https://hiresense-demo.vercel.app

## Calls to action

Use one call to action per post:

- **Feedback:** What would stop you from trying or self-hosting this?
- **Ranking:** Which matters most to you: match quality, explainability, or cost?
- **Product:** Which part of job searching should remain manual?
- **Contribution:** Is the contribution path clear enough for a first pull request?
- **Support:** If this is useful, star the repository so you can find future releases.

Do not combine all five in one post.
