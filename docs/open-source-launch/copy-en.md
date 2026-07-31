# English Publishing Copy

The copy is prefilled for **HireSense** and its public repository:

- Repository: <https://github.com/StevSant/HireSense>
- Live demo: <https://hiresense-demo.vercel.app>
- Architecture article: <https://github.com/StevSant/HireSense/blob/main/backend/ARCHITECTURE.md>

The live demo is frontend-only, read-only, and uses synthetic data. It requires no account
and is safe to share publicly.

Do not publish metrics or source counts without checking them immediately before posting.

## What's new (verified 2026-07-31)

Fresh material for the announcements. Name features, never unverified counts.

- **Opportunity Discover.** New `/opportunities` context: conferences, CFPs, and funded
  programs from confs.tech and curated imports. Filters by topic, country, deadline, and
  funded-only; sorting by relevance against your profile; and an attendance-cost label
  (`Free`, `Funded`, `Paid`, `Likely paid`) inferred even when the source publishes no fee.
- **New automated job sources:** Dice (official MCP), Y Combinator Work at a Startup
  (public JSON), and CrunchBoard (official RSS).
- **Opt-in, ToS-respecting imports** for Indeed, Wellfound, Glassdoor, and Monster, which
  have no usable public job-search API. No bot-wall or login bypassing.
- **Company portals:** adapters for Workday, Thoughtworks, and Globant, an `auto` detector
  that picks the right ATS from a careers URL, and a generic scraper with browser rendering
  for JavaScript-heavy sites.
- **Source transparency:** a per-source capability registry (`GET /ingestion/sources`) and
  per-source health with last run, counts, and errors (`GET /ingestion/sources/health`).
  Deduplication now records which sources saw each role and ranks direct ATS above
  aggregators.
- **Profile-aware ranking:** single and batch evaluation now use the profile you have
  selected instead of scoring without candidate context.
- **Sturdier ingestion:** long fetches and job revalidation run in the background instead of
  blocking the request.

## Opening hooks

A bank of first lines. Use one per post, and don't reuse the same one across networks.

- How many job-board tabs do you have open right now?
- Tired of digging through hundreds of listings to find the three that actually fit you?
- Your next job is probably already posted. It's just on page 40.
- Job hunting isn't an effort problem anymore. It's a noise problem.
- Your CV, salary expectations, and application history live in six different products. Are
  we all fine with that?
- Applying is the easy part. Figuring out what's worth applying to is the actual work.

## Core positioning

### Primary tagline

> Turn the job-board firehose into a private, ranked shortlist.

### Alternatives

- Hundreds of listings in. One shortlist that actually makes sense out.
- Your entire job search in one place — and that place is yours.

### One-sentence description

> HireSense is a self-hosted job-search workspace for candidates that ingests and
> deduplicates listings from job boards, company ATS portals, and now conferences, CFPs, and
> funded programs, ranks the whole corpus with pgvector and cost-aware LLM scoring, and
> manages applications end to end.

### GitHub About description

> Self-hosted job search for candidates: ingest and deduplicate listings, rank them with
> pgvector and LLMs, discover conferences and CFPs, and manage applications end to end.

### Social-preview text

```text
HireSense
Hundreds of listings in.
One shortlist that actually fits.
Open source · Self-hosted
```

## LinkedIn

The 8-slide carousel that goes with the primary post lives in
[`carousel/carousel-en.html`](carousel/carousel-en.html) — export it to PDF from Chrome. See
[`carousel/README.md`](carousel/README.md).

Remember that LinkedIn truncates after ~2–3 lines: the hook has to work on its own. The
primary post carries its two links (demo and repository) in the body on purpose — they are
the action being asked for. Any further link goes in the first comment.

### Primary launch post

> How many job tabs do you have open right now?
>
> I got to seven, several versions of my CV, and zero clarity on what was actually working.
> So I built **HireSense**.
>
> It's an **open-source, self-hosted** platform that:
>
> - Collects roles from job boards and company ATS portals, and removes duplicates.
> - Ranks them by how well they match your profile.
> - Manages applications, CVs, cover letters, and interviews.
> - Discovers conferences, CFPs, and funded programs.
>
> I made it self-hosted because your CV, salary expectations, and application history should
> stay under your control.
>
> **Stack:** Python, FastAPI, Angular, PostgreSQL/pgvector, Docker, LangChain, OpenTelemetry
> and Grafana.
>
> This is the first public release. I'd especially like to know:
>
> Is the installation clear?
> Does the job ranking actually feel useful?
>
> Demo: https://hiresense-demo.vercel.app/
> Repository: StevSant/HireSense
>
> If it's useful, a star or an issue on the repository helps a lot.
>
> #OpenSource #Python #JobSearch #AI #Jobs

### What's-new post

> A job posting isn't the only door.
>
> I just shipped **Discover** in HireSense: alongside job listings, it now finds
> conferences, CFPs, and funded programs, with filters by topic, country, and deadline,
> sorting by relevance against your profile, and a cost label that tells you whether it's
> free, funded, or paid — even when the source never publishes a fee.
>
> The same batch added new job sources: Dice, Y Combinator Work at a Startup, and
> CrunchBoard running automatically, plus adapters for Workday, Thoughtworks, and Globant
> portals and a detector that recognizes a company's ATS straight from its careers page.
>
> And something less flashy that I care about just as much: every source now reports its own
> health — last run, how many roles it returned, what error it hit — and deduplication
> records which sources saw each role, ranking the company's own ATS above aggregators.
>
> Still open source, still self-hosted: https://github.com/StevSant/HireSense
>
> Which source are you missing? It's literally one new adapter.
>
> #OpenSource #Python #JobSearch #DevCommunity

### Short follow-up post

> Your best match is on page 40, and you're never getting there.
>
> That's the real problem HireSense solves, and it has nothing to do with slapping "AI" on a
> product. It's about **when** ranking happens.
>
> If an app only scores the page you're currently looking at, a great role stays buried
> purely because it showed up late in the feed. So the pipeline semantically pre-ranks the
> full corpus before pagination.
>
> It uses pgvector for semantic pre-ranking, skill overlap as a fast structured signal, and
> tiered LLM scoring only where the extra cost buys real signal.
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

> Why should my CV and application history live on someone else's server? I built a
> self-hosted job-search workspace with pgvector ranking

**Body**

> I wanted a job-search workflow where my CV, preferences, salary expectations, and
> application history did not have to live in another SaaS product that also monetizes them,
> so I built HireSense.
>
> It ingests roles from public job boards and company ATS portals, deduplicates them by
> stable identity, ranks the full corpus with pgvector plus skill and optional LLM scoring,
> and tracks applications through interview and offer stages. It also includes tailored
> document generation, interview preparation, scheduling, analytics, and
> OpenTelemetry/Grafana observability.
>
> Recent additions: new sources (Dice, YC Work at a Startup, CrunchBoard), Workday /
> Thoughtworks / Globant portal adapters with an auto-detector for unknown careers pages, a
> per-source health endpoint so you can see which ingestion broke without opening logs, and
> a Discover section for conferences, CFPs, and funded programs.
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

> I'm preparing the first public release of HireSense, a self-hosted job-search system built
> around FastAPI, Angular, PostgreSQL/pgvector, and a hexagonal backend architecture.
>
> The repository already includes an MIT license, security policy, contribution guide, Code
> of Conduct, issue forms, CI, and architecture documentation. The main contribution areas
> are source adapters, ranking quality, onboarding, accessibility, and documentation.
>
> Source adapters in particular are a genuinely good first contribution: each one is a port
> implementation plus a normalizer plus a capability entry, with a documented recipe in
> `docs/job-sources.md` and unit tests that never hit the live network.
>
> Repository: https://github.com/StevSant/HireSense
>
> I am especially interested in feedback from maintainers: is the contribution path clear,
> and which small issue would make the best first external contribution?

### `r/SideProject`

**Title**

> Applying is the easy part — I turned the hard part of job hunting into an open-source app

**Body**

> My job search kept expanding into separate spreadsheets, job-board tabs, CV copies,
> interview notes, and reminders. I started HireSense to put that workflow in one place.
>
> The most interesting engineering problem was not generating text. It was reducing the
> firehose: deduplicating jobs, ranking the complete corpus instead of one page, controlling
> LLM cost, and keeping listings current when sources change or disappear.
>
> It has grown into a FastAPI + Angular application with PostgreSQL/pgvector, Docker,
> application tracking, tailored artifacts, interview preparation, analytics, automation,
> and observability — plus a recent Discover section for conferences, CFPs, and funded
> programs, because not every career move is an application.
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
> listings, ranks them against your profile, surfaces relevant conferences and CFPs, and
> supports the application process from tailored documents to interview preparation and
> analytics.

### Maker first comment

> Hi Product Hunt — how many job-board tabs do you have open right now?
>
> I built HireSense after realizing that job hunting had become a collection of disconnected
> tools: job boards for discovery, spreadsheets for tracking, document copies for every
> application, separate interview notes, and no useful view of what was working.
>
> The core idea is to reduce noise before adding more automation. HireSense ingests roles
> from public boards and company ATS portals, deduplicates them, semantically pre-ranks the
> complete corpus with pgvector, and uses skill matching and optional tiered LLM scoring to
> build a shortlist.
>
> It then supports the workflow around that shortlist: tracking, tailored CVs and cover
> letters, interview preparation, outreach, automation, and market analytics. A recent
> addition surfaces conferences, CFPs, and funded programs with a cost label, since a talk
> or a program can move a career as much as an application does.
>
> It is MIT-licensed and self-hosted because candidate data is personal. The public preview
> source code is available at https://github.com/StevSant/HireSense.
>
> I would value feedback on two things: whether the first-run experience is clear, and which
> part of the job-search workflow you would want to automate — or deliberately keep manual.

Do not ask anyone to upvote. Invite people to try it and comment.

## Show HN

Hacker News currently prohibits generated or AI-edited comments. Do not paste a generated
submission from this file. Write the final text personally after reading the current
[Show HN guidelines](https://news.ycombinator.com/showhn.html) and
[general guidelines](https://news.ycombinator.com/newsguidelines.html).

Note that HN dislikes marketing hooks. Do not carry the question openers from this file into
a Show HN post — use a plain, factual title:

```text
Show HN: HireSense – Self-hosted job search with pgvector and tiered LLM scoring
```

Write a short discussion in your own words covering:

1. The personal frustration that started the project.
2. What someone can try immediately and how.
3. Why whole-corpus ranking differs from scoring only a visible page.
4. How pgvector, skill signals, and tiered models balance quality and cost.
5. Why the project is self-hosted.
6. Which sources are genuinely automatable versus import-only, and why.
7. One limitation or unfinished area you genuinely want feedback on.

Avoid emoji, marketing adjectives, unsupported metrics, and requests for votes or comments.
Stay available to answer technical questions after submitting.

## DEV Community / Hashnode

### Recommended article

**Title**

> Your best match is on page 40: building a cost-aware job-ranking pipeline with pgvector
> and tiered LLM scoring

**Subtitle**

> Why ranking the whole corpus before pagination produced a better shortlist — and how cheap
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
- When the source won't tell you the price: inferring whether a conference is free, funded,
  or paid
- Seven job boards, seven ways of saying no: what you can actually integrate and what you
  have to import by hand
- Designing a self-hosted AI application around candidate privacy
- Stable identity, content hashes, and the surprisingly hard problem of stale job listings
- Using hexagonal architecture in a FastAPI application with many external adapters
- Instrumenting LLM calls with OpenTelemetry, Tempo, Loki, and Grafana

## Short social copy

### X / Bluesky / Mastodon

> Your next job is probably already posted. It's on page 40 and you're never getting there.
>
> So I built HireSense: open source, self-hosted, deduplicates listings, ranks **the whole
> corpus** with pgvector before paginating, finds conferences and CFPs, and manages
> applications end to end.
>
> Source: https://github.com/StevSant/HireSense
>
> Demo: https://hiresense-demo.vercel.app

### Short variant (what's new)

> New in HireSense: Discover for conferences, CFPs, and funded programs — filter by topic,
> country, and deadline, with a cost label even when the source never publishes a fee.
>
> Plus new job sources: Dice, YC Work at a Startup, and CrunchBoard.
>
> https://github.com/StevSant/HireSense

### YouTube title

> I built the app I wish I'd had while job hunting (FastAPI + Angular + pgvector)

### YouTube description

> Tired of scrolling hundreds of listings to find three that fit? HireSense turns that
> firehose into a deduplicated shortlist ranked against your profile, then supports
> application tracking, tailored documents, interview preparation, outreach, and analytics.
> It also surfaces conferences, CFPs, and funded programs.
>
> Source code and documentation: https://github.com/StevSant/HireSense
>
> Live demo: https://hiresense-demo.vercel.app

## Calls to action

Use one call to action per post:

- **Feedback:** What would stop you from trying or self-hosting this?
- **Ranking:** Which matters most to you: match quality, explainability, or cost?
- **Product:** Which part of job searching should remain manual?
- **Sources:** Which job board are you missing? Adding one is a single new adapter.
- **Contribution:** Is the contribution path clear enough for a first pull request?
- **Support:** If this is useful, star the repository so you can find future releases.

Do not combine all of them in one post.

## Wording guidance

Hooks can be direct and have personality, but the promise underneath must stay checkable:
describe what the tool does, not what it guarantees you'll get. Avoid "revolutionary",
"guarantees interviews", "beats any ATS", "auto-applies to everything", "replaces
recruiters", and any accuracy or savings claim without a verifiable measurement.
