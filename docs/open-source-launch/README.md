# Open-Source Launch Strategy

Last reviewed: 2026-07-22

This kit turns HireSense's public repository into a deliberate open-source launch for two
audiences: developers who may use or contribute to it, and recruiters or engineering
managers who may value the product and engineering work.

## Launch kit

- [Launch checklist](launch-checklist.md)
- [English publishing copy](copy-en.md)
- [Spanish publishing copy](copy-es.md)

## Current state

HireSense is already technically open source: the repository is public, uses the MIT
license, and includes contribution guidelines, a Code of Conduct, a security policy, issue
templates, Docker configuration, screenshots, and architectural documentation.

It is stronger than a typical portfolio demo. Its public story includes multi-source job
ingestion, stable-identity deduplication, whole-corpus pgvector ranking, skill and tiered LLM
scoring, application tracking, document generation, interview preparation, outreach,
automation, analytics, and observability. The remaining problem is packaging and
distribution, not a lack of substantive engineering.

## Before launch

### 1. Resolve the product name

At least two active hiring-related businesses already use the HireSense name:

- [HireSense](https://www.hiresense.com/)
- [HireSense.ai](https://www.linkedin.com/company/hiresense-ai)

The collision makes search discovery, social handles, and word of mouth harder and may
create trademark concerns. This is not a legal determination. Before investing in launch
assets, choose and clear a distinctive name or obtain appropriate advice and consistently
distinguish this candidate-side open-source project.

### 2. Make the first run genuinely easy

The README presents `docker compose up --build` as the trial path and says an LLM key is
optional in local mode. Compose forces `APP_MODE=production`, loads `backend/.env`, and
requires database and application secrets. That creates a first-run contradiction.

Before launch:

- test installation from a fresh clone on a clean machine;
- put every required copy and configuration command in one quick start;
- provide a demo configuration that does not require a paid LLM key;
- seed synthetic profile, job, application, and analytics data; and
- aim for one command after initial configuration, with actionable errors.

A hosted read-only demo with synthetic data is now available at
<https://hiresense-demo.vercel.app>. It has no backend connection, account requirement,
personal CVs, contacts, email signals, credentials, or provider keys.

### 3. Make LinkedIn ingestion explicitly experimental

The repository describes its LinkedIn guest-endpoint adapter as fragile and ToS-risky, yet
it is part of the default enabled sources. Disable it by default, label it experimental and
opt-in, document markup and rate-limit risks, and require operators to respect source terms,
robots policies, rate limits, and applicable law.

In launch copy, say “public job boards and company ATS portals.” Do not make LinkedIn
scraping a headline. The operator-supplied LinkedIn data-export import is a different feature
and should be described separately.

### 4. Publish a real release

Create a `v0.1.0` public-preview release rather than promoting an unversioned branch. Include
the intended audience, supported versus experimental features, exact requirements, known
limitations, screenshots, demo, and links to contribution and security guidance. GitHub
documents the available packaging and release-note features in
[Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

### 5. Create launch-quality visual assets

Prepare a 60–90 second walkthrough, a 20–30 second silent captioned cut, three current
screenshots with synthetic data, and a 1280×640 social card. The walkthrough should show one
coherent journey: profile, ranked shortlist, score explanation, application tracking,
tailored artifact, and interview preparation or analytics.

GitHub recommends 1280×640 for the best social-preview rendering. See
[GitHub's social-preview guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview).

### 6. Tighten repository credibility

- Update Angular references to the version declared in `frontend/package.json`.
- Ensure the Python badge agrees with `backend/pyproject.toml`.
- Complete or remove the instructional author placeholder in `CITATION.cff`.
- Add a CI badge after confirming the public workflow is green.
- Put the documentation or demo URL in GitHub's **About** section.
- Confirm every screenshot contains synthetic data and no personal details.
- Add a short `Now / Next / Later` roadmap.
- Label several small issues `good first issue` and `help wanted`.

### 7. Improve GitHub discovery

Use accurate repository topics such as:

```text
self-hosted, job-search, job-application-tracker, career-tools, resume-builder,
semantic-search, pgvector, llm, fastapi, angular, python, typescript, postgresql,
docker, open-source
```

GitHub permits up to 20 topics and uses them for repository discovery. See
[Repository topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics).

## Three approaches

### Portfolio-first

Lead with the personal story and engineering decisions on LinkedIn. This is the fastest path
to recruiter and hiring-manager visibility, but may create profile views without many
long-term users or contributors.

### Open-source-community-first

Lead with GitHub, Show HN, technical articles, and carefully selected Reddit communities.
This is strongest for technical feedback, stars, contributors, and credibility, but demands
a reliable setup and active maintainer participation.

### Product-first

Lead with a polished landing page, hosted demo, Product Hunt, onboarding, and user outcomes.
This reaches early adopters beyond developers but requires the most launch work and creates
support expectations immediately.

## Recommended rollout

Use a staged combination:

1. Resolve naming, fix onboarding, publish `v0.1.0`, and prepare visuals.
2. Publish the English LinkedIn post, then Spanish two or three days later.
3. Publish a focused architecture or ranking article on DEV Community or Hashnode.
4. Write one community-specific Reddit post rather than copying LinkedIn.
5. Submit Show HN once the application is genuinely easy to try.
6. Use Product Hunt after a hosted demo or exceptionally smooth local demo exists.
7. Continue with useful releases, lessons, and contributor stories.

Do not publish identical promotional text everywhere on the same day. Staggering the launch
lets feedback from one audience improve the next artifact.

## Where to publish

| Priority | Channel | Best audience | Publish when | Best content |
|---:|---|---|---|---|
| 1 | LinkedIn | Recruiters, managers, professional network | Release and demo are ready | Personal story plus native video |
| 2 | `r/selfhosted` | Self-hosters and operators | Installation is reliable | Privacy, deployment, and architecture |
| 3 | `r/opensource` | Maintainers and contributors | Contribution path is clear | Scope, governance, and requested help |
| 4 | `r/SideProject` | Builders and early adopters | Demo is understandable | Problem, build story, and lessons |
| 5 | DEV / Hashnode | Developers and search traffic | A technical lesson is ready | Deep article, not an advertisement |
| 6 | Show HN | Technical early adopters | People can try it easily | Honest build story and trade-offs |
| 7 | Product Hunt | Makers and product early adopters | Hosted demo and polished assets exist | Benefits, gallery, and maker story |
| 8 | YouTube | Searchable demos and future users | Walkthrough is recorded | Full demo and focused technical videos |
| 9 | X / Bluesky / Mastodon | Existing followers | Any meaningful milestone | Short clips and release notes |
| 10 | Curated lists | Durable, intent-driven discovery | Project is stable and eligible | Concise factual listing |

For Spanish-speaking audiences, prioritize the Spanish LinkedIn post, `r/programacion`, and
developer communities in which the maintainer already participates. Community trust matters
more than posting to the largest possible number of groups. Always reread current community
rules immediately before submitting.

### Platform cautions

- **LinkedIn:** Attach native video and ask one concrete feedback question. LinkedIn supports
  posts, video, images, documents, and articles. See
  [LinkedIn's posting guide](https://www.linkedin.com/help/linkedin/answer/a518996).
- **Reddit:** Do not paste the same promotion into several communities. Explain why the
  project belongs in the selected community and participate beyond self-promotion.
- **Show HN:** The project must be something people can try, ideally without signup or email
  barriers. Never solicit votes or comments. Hacker News also prohibits generated or
  AI-edited comments, so use this kit only as research and write the final HN submission in
  the maintainer's own words. See the
  [Show HN guidelines](https://news.ycombinator.com/showhn.html).
- **DEV:** Use an accurate title and four relevant tags. Teach a reusable lesson before
  linking to the repository. See
  [DEV's publishing guide](https://dev.to/devteam/writing-your-first-post-on-dev-3m13/).
- **Product Hunt:** Submit only a usable product. Ask supporters to visit, comment, or share
  feedback, never to upvote. See the
  [Product Hunt launch guide](https://www.producthunt.com/launch).

## Positioning

### Primary promise

**English:** Turn the job-board firehose into a private, ranked shortlist.

**Spanish:** Convierte el caos de los portales de empleo en una lista privada, ordenada y
relevante.

### Supporting description

**English:** A self-hosted job-search workspace for candidates that ingests and deduplicates
listings, ranks the whole corpus with pgvector and cost-aware LLM scoring, and manages the
application workflow end to end.

**Spanish:** Una plataforma autoalojable para candidatos que reúne y deduplica vacantes,
ordena todas las oportunidades con pgvector y evaluación eficiente con LLMs, y gestiona las
postulaciones de principio a fin.

### Words and ideas to use

- Candidate-side, not recruiter-side.
- Self-hosted, private, and under your control.
- Ranked shortlist rather than more search results.
- Whole-corpus semantic ranking.
- Deduplication and listing lifecycle.
- Cost-aware, tiered LLM scoring.
- End-to-end workflow.
- Open source, transparent, and contributor-friendly.
- AI-assisted rather than magical or autonomous.

### Words and claims to avoid

- Revolutionary, game-changing, or perfect.
- Guaranteed interviews or job offers.
- Beats every ATS or makes a CV ATS-proof.
- Fully autonomous applications.
- Replaces recruiters.
- Completely private if a configured provider receives candidate or job data.
- Free when providers or infrastructure may incur costs.
- Speed, accuracy, savings, source-count, or test-count claims not measured immediately
  before publication.

## Content that compounds after launch

One announcement rarely creates durable attention. Publish useful artifacts such as:

- Why whole-corpus ranking matters more than scoring the current page.
- How stable identity and content hashes prevent duplicate or stale jobs.
- How tiered LLM scoring controls cost.
- Why the domain layer is isolated from infrastructure.
- Why the LinkedIn adapter became experimental.
- How heuristic mode works without an LLM key.
- How OpenTelemetry, Loki, Tempo, and Grafana expose LLM and API behavior.
- A release retrospective with installation and engagement data.
- A contributor story after the first external pull request.

## Measure the launch

Choose a small scorecard before publishing:

- Unique repository visitors and traffic sources.
- Stars, forks, clones, and watchers.
- Demo views and completion rate.
- Successful clean-machine installations.
- Actionable issues and external pull requests.
- LinkedIn impressions, profile views, saves, and meaningful comments.
- Article reads and referral traffic.

Use a distinct tracked link per channel when linking through a landing page. Treat stars as
an interest signal, not the only success measure. Successful installations, recurring users,
useful issues, and external contributions are stronger long-term indicators.

## Official references

- [Current repository](https://github.com/StevSant/HireSense)
- [GitHub topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
- [GitHub social previews](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)
- [GitHub releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [LinkedIn posting options](https://www.linkedin.com/help/linkedin/answer/a518996)
- [Show HN guidelines](https://news.ycombinator.com/showhn.html)
- [Hacker News guidelines](https://news.ycombinator.com/newsguidelines.html)
- [DEV publishing guide](https://dev.to/devteam/writing-your-first-post-on-dev-3m13/)
- [Product Hunt launch guide](https://www.producthunt.com/launch)
