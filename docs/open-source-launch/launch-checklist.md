# Open-Source Launch Checklist

Use this with the [strategy](README.md), [English copy](copy-en.md), and
[Spanish copy](copy-es.md). Dates are relative so the checklist remains reusable.

## Phase 1: Foundation

### Name and ownership

- [ ] Search the name across search engines, GitHub, package registries, domains, and social networks.
- [ ] Search relevant official trademark databases in the jurisdictions where it may operate.
- [ ] Decide whether to rename or obtain appropriate clearance before creating launch assets.
- [ ] Reserve the final domain and important social handles.
- [ ] Update the repository, logo, descriptions, documentation, and screenshots if renamed.
- [ ] Complete or remove the instructional author placeholder in `CITATION.cff`.

### Installation and demo

- [ ] Clone the repository into a clean directory without developer secrets.
- [ ] Follow only the public README and record every unclear or missing step.
- [ ] Reconcile the README's no-key promise with Compose's production requirements.
- [ ] Put the complete trial setup in one copy-pasteable sequence.
- [ ] Make errors identify the missing file or variable and its corrective action.
- [ ] Provide a no-paid-LLM trial path.
- [x] Seed synthetic profile, job, application, analytics, and artifact data.
- [x] Deploy and verify the read-only demo: <https://hiresense-demo.vercel.app>.
- [x] Verify the demo contains no real CV, contact, email, salary, or credential data.
- [ ] Repeat the clean-machine installation using only the revised instructions.
- [ ] Document only operating systems and prerequisites actually tested.

### Source policy and safety

- [ ] Disable the LinkedIn guest-endpoint scraper by default.
- [ ] Label LinkedIn scraping experimental and opt-in.
- [ ] Document markup-breakage and rate-limit risks.
- [ ] Require operators to respect source terms, robots policies, rate limits, and law.
- [ ] Distinguish live ingestion from operator-supplied LinkedIn export import.
- [ ] Confirm `.env`, CVs, generated files, browser reports, and scratch screenshots are ignored.
- [ ] Scan the repository and Git history for accidentally committed secrets or personal data.
- [ ] Verify private vulnerability reporting works as described in `SECURITY.md`.

### Repository presentation

- [ ] Update Angular references to match `frontend/package.json`.
- [ ] Confirm the Python badge matches `backend/pyproject.toml`.
- [ ] Add a green CI badge after the public workflow succeeds.
- [ ] Confirm screenshots are current and use synthetic data.
- [ ] Add a concise `Now / Next / Later` roadmap.
- [ ] Add the documentation or demo URL to GitHub's **About** section.
- [ ] Add accurate GitHub topics from the strategy.
- [ ] Enable GitHub Discussions if maintainer capacity exists.
- [ ] Create three to five small, self-contained issues.
- [ ] Label appropriate issues `good first issue` and `help wanted`.
- [ ] Confirm the contribution guide takes a newcomer from clone to passing checks.

## Phase 2: Release package

- [ ] Choose the release commit after required checks pass.
- [ ] Create a `v0.1.0` public-preview tag and GitHub release draft.
- [ ] State the candidate-side audience and problem.
- [ ] List stable features separately from experimental integrations.
- [ ] Include exact installation requirements and known limitations.
- [ ] Include screenshots and the walkthrough.
- [ ] Link contribution, security, architecture, and roadmap documentation.
- [ ] Mention contributors where appropriate.
- [ ] Proofread the release from a signed-out browser.
- [ ] Publish only after every linked asset is public and working.

## Phase 3: Visual assets

- [ ] Create a 1280×640 GitHub social preview under 1 MB.
- [ ] Use a solid background that works in light and dark contexts.
- [ ] Include the final name, primary promise, and one readable interface crop.
- [ ] Record a 60–90 second walkthrough with synthetic data.
- [ ] Create a 20–30 second captioned cut for social feeds.
- [ ] Add accurate English captions.
- [ ] Add accurate Spanish captions or separate Spanish narration.
- [ ] Export a thumbnail with readable text at mobile size.
- [ ] Test every video without sound.

## Phase 4: Publishing

### Week 1: LinkedIn

- [ ] Publish the English post with native short video.
- [ ] Keep it public and verify the repository preview.
- [ ] Ask one concrete question about setup or ranking.
- [ ] Respond substantively to useful comments.
- [ ] Record recurring questions for README improvements.
- [ ] Publish Spanish two or three days later.
- [ ] Adapt the Spanish story to Latin American candidates instead of translating mechanically.

### Week 2: Technical article

- [ ] Choose one reusable lesson rather than a complete product tour.
- [ ] Publish on DEV, Hashnode, or the maintainer's blog.
- [ ] Use an accurate technical title and relevant tags.
- [ ] Explain the problem, constraints, design, failure modes, and measured result.
- [ ] Link the repository after the article has delivered independent value.
- [ ] Convert recurring questions into documentation.

### Week 3: Reddit

- [ ] Read the selected community's current rules immediately before posting.
- [ ] Choose only one primary Reddit community for the first post.
- [ ] Rewrite the post around that community's interests.
- [ ] For `r/selfhosted`, emphasize privacy, deployment, dependencies, and operations.
- [ ] For `r/opensource`, emphasize license, architecture, governance, and contribution needs.
- [ ] For `r/SideProject`, emphasize the personal problem, build journey, and lessons.
- [ ] For `r/programacion`, use the Spanish draft and answer in Spanish.
- [ ] Do not solicit votes or coordinate engagement.
- [ ] Wait before posting elsewhere and incorporate the first round of feedback.

### Week 4: Show HN

- [ ] Confirm a signed-out visitor can try the project without an email gate.
- [ ] Read the current Show HN and general Hacker News guidelines.
- [ ] Write the final title and discussion personally, without generated or AI-edited prose.
- [ ] Explain why it exists and which technical trade-offs were interesting.
- [ ] Avoid marketing adjectives, emoji, engagement requests, and unsupported claims.
- [ ] Be available for several hours after submitting.
- [ ] Answer criticism with technical detail and curiosity.
- [ ] Do not ask friends or followers to vote or comment.

### Later: Product Hunt

- [ ] Wait for a hosted demo or exceptionally smooth local demo.
- [ ] Verify the product is usable, not a waitlist or landing page.
- [ ] Prepare the name, tagline, gallery, video, topics, maker profile, and first comment.
- [ ] Tell the personal maker story in the first comment.
- [ ] Ask supporters to visit and comment, never to upvote.
- [ ] Remain present throughout launch day.
- [ ] Publish a transparent launch retrospective.

## Phase 5: Long-term discovery

- [ ] Publish meaningful releases rather than promoting every small commit.
- [ ] Publish one reusable technical lesson or product insight regularly.
- [ ] Turn recurring support questions into documentation.
- [ ] Thank and highlight external contributors.
- [ ] Submit to curated lists only after meeting every contribution rule.
- [ ] Keep screenshots, supported versions, and setup instructions accurate.
- [ ] Close or label stale issues so the contribution surface stays trustworthy.

## Measurement

- [ ] Capture the pre-launch baseline for stars, forks, visitors, clones, and issues.
- [ ] Use a separate tracked landing-page link for each channel where practical.
- [ ] Record LinkedIn impressions, profile views, saves, and substantive comments.
- [ ] Record demo views and completion rate.
- [ ] Count verified clean-machine installations.
- [ ] Count actionable bug reports and product feedback separately.
- [ ] Count external contributors and merged pull requests.
- [ ] Review results after one week and one month.
- [ ] Record which channel produced users or contributors, not just impressions.
- [ ] Choose the next content topic from actual questions and usage data.

## Launch-day stop conditions

Pause promotion if any of these statements is true:

- [ ] The public quick start cannot produce a running application.
- [ ] A screenshot or demo contains personal information.
- [ ] The release points to private, broken, or missing assets.
- [ ] CI is failing for a release-blocking reason.
- [ ] A source integration creates an unaddressed terms, privacy, or security concern.
- [ ] The name decision is still likely to force an immediate rebrand.
