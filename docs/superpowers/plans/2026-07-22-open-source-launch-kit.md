# Open-Source Launch Kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved HireSense launch recommendations into a navigable Markdown kit with an audit, rollout checklist, and ready-to-adapt English and Spanish copy.

**Architecture:** Keep strategic guidance in one index, operational steps in a checklist, and channel-specific writing in separate language files. Cross-link the four files so a maintainer can move from preparation to publication without duplicating guidance.

**Tech Stack:** GitHub-flavored Markdown, repository-relative links, external links to official platform guidance

## Global Constraints

- Do not modify application code or configuration.
- Treat `HireSense` as the current working name while clearly recording the naming collision and recommending clearance or renaming before launch.
- Do not describe the LinkedIn guest-endpoint scraper as a safe or supported integration.
- Do not promise interviews, job offers, ATS success, or fully autonomous applications.
- Use placeholders only where the publisher must supply a final project name or public URL, and label those placeholders explicitly.
- Do not commit or publish the documentation without the repository owner's explicit request.

---

### Task 1: Launch strategy and repository audit

**Files:**
- Create: `docs/open-source-launch/README.md`

**Interfaces:**
- Consumes: Existing repository README, Docker configuration, package metadata, and the approved launch recommendations
- Produces: The index and source of truth linked by the checklist and language-specific copy files

- [ ] **Step 1: Write the strategy document**

Include the current-state assessment, launch blockers, three rollout approaches, recommended staged approach, channel priorities, positioning vocabulary, success metrics, and official references.

- [ ] **Step 2: Verify required sections**

Run:

```powershell
rg -n "Current state|Before launch|Recommended rollout|Where to publish|Positioning|Measure" docs/open-source-launch/README.md
```

Expected: one or more matches for every named section.

### Task 2: Operational launch checklist

**Files:**
- Create: `docs/open-source-launch/launch-checklist.md`

**Interfaces:**
- Consumes: Priorities and cautions from `docs/open-source-launch/README.md`
- Produces: A checkable four-week rollout with pre-launch, launch-day, and follow-up actions

- [ ] **Step 1: Write the checklist**

Include naming, onboarding, data hygiene, scraper policy, release packaging, social assets, GitHub metadata, community preparation, weekly publishing, and post-launch measurement.

- [ ] **Step 2: Verify checklist syntax**

Run:

```powershell
rg -n "^- \[ \]" docs/open-source-launch/launch-checklist.md
```

Expected: actionable unchecked items across all phases.

### Task 3: English publishing copy

**Files:**
- Create: `docs/open-source-launch/copy-en.md`

**Interfaces:**
- Consumes: Positioning from `docs/open-source-launch/README.md`
- Produces: English GitHub description, tagline, LinkedIn post, Reddit drafts, Product Hunt copy, DEV/Hashnode titles, and a non-paste-ready Show HN outline

- [ ] **Step 1: Write the English copy**

Keep claims supportable from the repository. Mark `[PROJECT NAME]`, `[REPOSITORY URL]`, and `[DEMO URL]` as publisher-supplied values.

- [ ] **Step 2: Verify channels and placeholders**

Run:

```powershell
rg -n "LinkedIn|Reddit|Product Hunt|Show HN|DEV|PROJECT NAME|REPOSITORY URL" docs/open-source-launch/copy-en.md
```

Expected: every launch channel and required publisher-supplied value is present.

### Task 4: Spanish publishing copy

**Files:**
- Create: `docs/open-source-launch/copy-es.md`

**Interfaces:**
- Consumes: Positioning from `docs/open-source-launch/README.md`
- Produces: Natural Spanish copy adapted for Latin American candidates and developer communities

- [ ] **Step 1: Write the Spanish copy**

Use natural terms such as `autoalojable`, `vacantes`, `postulaciones`, and `búsqueda laboral`; do not translate mechanically from English.

- [ ] **Step 2: Verify channels and vocabulary**

Run:

```powershell
rg -n "LinkedIn|Reddit|Product Hunt|DEV|autoalojable|vacantes|postulaciones|búsqueda laboral" docs/open-source-launch/copy-es.md
```

Expected: every channel and required vocabulary item is present.

### Task 5: Cross-link and review the kit

**Files:**
- Modify: `docs/open-source-launch/README.md`
- Verify: `docs/open-source-launch/launch-checklist.md`
- Verify: `docs/open-source-launch/copy-en.md`
- Verify: `docs/open-source-launch/copy-es.md`

**Interfaces:**
- Consumes: All four completed launch-kit files
- Produces: A self-contained, navigable documentation bundle

- [ ] **Step 1: Add navigation links to the index**

Link the checklist and both copy libraries near the top of `docs/open-source-launch/README.md`.

- [ ] **Step 2: Scan for accidental unfinished text**

Run:

```powershell
rg -n "TBD|TODO|FIXME|lorem ipsum" docs/open-source-launch
```

Expected: no matches.

- [ ] **Step 3: Inspect the final diff**

Run:

```powershell
git diff --check
git diff -- docs/open-source-launch docs/superpowers/plans/2026-07-22-open-source-launch-kit.md
```

Expected: `git diff --check` exits successfully, and the diff contains documentation changes only.
