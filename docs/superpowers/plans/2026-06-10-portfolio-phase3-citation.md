# Portfolio Phase 3 (Artifact Citation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cover letters and outreach messages cite the 1–2 most relevant portfolio projects for the specific job and include a per-application tracked portfolio link (`{PORTFOLIO_PUBLIC_URL}/?ref={PORTFOLIO_REF_PREFIX}-{application_id}`).

**Architecture:** Pure `RelevantProjectSelector` + `PortfolioCitationService` in the portfolio domain, exposed via the provider; `ApplyService` (cover letters) and `OutreachService` gain an OPTIONAL `portfolio_citation` collaborator wired in `main.py`/bootstrap — None ⇒ byte-identical prompts to today. The generated text itself shows the citations (no new persistence/UI; structured "which projects were cited" display deferred — the letter body is visible in the existing UI).

**Working directory:** `C:\Users\Bryan\worktrees\hiresense-portfolio` (branch `feat/portfolio-citation`, stacked on `feat/portfolio-github`; PR base = that branch). Backend from `backend/`. **Quirks:** `uv run python -m pytest` only (never bare `uv run pytest`); no repo-wide `ruff format`; commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

**Codebase facts (verified):**
- Cover letter: `applications/domain/apply_service.py:36-80` (`generate_cover_letter(application_id, cv_language, tone)`; has `snapshot.description` + `snapshot.required_skills`); prompt in `applications/domain/cover_letter_generator.py` (`USER_PROMPT_TEMPLATE`, "Constraints:" section). Built in `bootstrap/applications.py` (`CoverLetterGenerator(llm=tracked("cover_letter"))`, `ApplyService(...)`).
- Outreach: `outreach/domain/outreach_service.py:39-58` (`generate(application_id, *, contact_name, channel)`; has `app.notes` as job text, NO skills); prompt parts list in `outreach/domain/message_generator.py:44-65` with existing `if x: parts.append(...)` optional-section pattern; service holds `self._language` from config. Built in `bootstrap/outreach.py`.
- `main.py` builds portfolio BEFORE applications and outreach — pass `portfolio.provider.get_citation_service() if portfolio is not None else None` into both builders.
- Portfolio domain already has `PortfolioProject.text_for(language)`, `PortfolioProjectsRepositoryPort.list_all`, provider with getters, bootstrap `build_portfolio`.

---

### Task 1: Config + env

**Files:** `backend/src/hiresense/config.py`, `backend/.env`, `backend/.env.example`, `backend/tests/unit/test_config.py`

- [ ] **Step 1: failing test** — append to `test_config.py`:

```python
def test_portfolio_citation_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_PUBLIC_URL", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.portfolio_public_url == ""
    assert settings.portfolio_ref_prefix == "hiresense"
    assert settings.portfolio_relevant_projects_top_n == 2
```

- [ ] **Step 2:** run it → FAIL. **Step 3:** add to the portfolio block in `config.py` (after `portfolio_github_max_repos`):

```python
    # Public portfolio site linked from generated artifacts. Empty disables
    # the tracked link (project citations still work).
    portfolio_public_url: str = ""
    # Slug prefix for per-application tracked links: ?ref=<prefix>-<application_id>.
    portfolio_ref_prefix: str = "hiresense"
    # How many relevant projects get cited per generated artifact.
    portfolio_relevant_projects_top_n: int = 2
```

- [ ] **Step 4:** test file green. **Step 5:** `.env.example` gains the three vars (commented, `PORTFOLIO_PUBLIC_URL=` empty placeholder); local `backend/.env` gains them with `PORTFOLIO_PUBLIC_URL=https://your-portfolio.example.com`, others default.
- [ ] **Step 6: commit** — `feat(portfolio): citation settings`.

---

### Task 2: RelevantProjectSelector (pure)

**Files:** create `backend/src/hiresense/portfolio/domain/relevant_project_selector.py`; modify `domain/__init__.py`; test `backend/tests/unit/portfolio/test_relevant_project_selector.py`

- [ ] **Step 1: failing test:**

```python
from hiresense.portfolio.domain import PortfolioProject, ProjectText, RelevantProjectSelector


def _project(key, *, tech=None, title=None, pinned=False, position=None):
    return PortfolioProject(
        id=key, source="supabase", source_key=key, pinned=pinned, position=position,
        tech=tech or [],
        translations={"en": ProjectText(title=title or key, description="d")},
    )


def test_ranks_by_term_overlap_and_drops_irrelevant() -> None:
    selector = RelevantProjectSelector()
    projects = [
        _project("nest", tech=["nestjs", "kafka"]),
        _project("ai", tech=["fastapi", "langchain", "postgresql"]),
        _project("unrelated", tech=["unity", "csharp"]),
    ]
    picked = selector.select(
        job_skills=["FastAPI", "PostgreSQL"],
        job_text="We use LangChain agents over Postgres.",
        projects=projects,
        top_n=2,
    )
    assert [p.source_key for p in picked] == ["ai"]  # zero-overlap projects are dropped


def test_title_tokens_count_and_pinned_breaks_ties() -> None:
    selector = RelevantProjectSelector()
    projects = [
        _project("b", tech=["python"], position=2),
        _project("a", tech=["python"], pinned=True, position=9),
    ]
    picked = selector.select(job_skills=["python"], job_text="", projects=projects, top_n=2)
    assert [p.source_key for p in picked] == ["a", "b"]  # equal score -> pinned first

    titled = selector.select(
        job_skills=[], job_text="building a kafka pipeline",
        projects=[_project("k", title="kafka-dashboard"), _project("x", title="todo-app")],
        top_n=2,
    )
    assert [p.source_key for p in titled] == ["k"]


def test_top_n_caps_results() -> None:
    selector = RelevantProjectSelector()
    projects = [_project(f"p{i}", tech=["python"]) for i in range(5)]
    assert len(selector.select(job_skills=["python"], job_text="", projects=projects, top_n=2)) == 2
```

- [ ] **Step 2:** run → FAIL. **Step 3: implement** `relevant_project_selector.py`:

```python
from __future__ import annotations

import re

from hiresense.portfolio.domain.portfolio_project import PortfolioProject

_TOKEN_RE = re.compile(r"[a-z0-9_+#.]+")
_UNPOSITIONED = 1_000_000


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class RelevantProjectSelector:
    """Ranks portfolio projects against a job, deterministically (no LLM).

    Score = overlap between the job's terms (skills + description tokens) and
    the project's terms (tech + title tokens). Zero-score projects are never
    cited; ties break pinned-first, then by position.
    """

    def select(
        self,
        *,
        job_skills: list[str],
        job_text: str,
        projects: list[PortfolioProject],
        top_n: int,
    ) -> list[PortfolioProject]:
        job_terms = {skill.lower() for skill in job_skills} | _tokens(job_text)
        scored: list[tuple[int, PortfolioProject]] = []
        for project in projects:
            title = project.text_for("en")
            project_terms = {tech.lower() for tech in project.tech}
            if title is not None:
                project_terms |= _tokens(title.title)
            score = len(project_terms & job_terms)
            if score > 0:
                scored.append((score, project))
        scored.sort(
            key=lambda pair: (
                -pair[0],
                not pair[1].pinned,
                pair[1].position if pair[1].position is not None else _UNPOSITIONED,
            )
        )
        return [project for _, project in scored[:top_n]]
```

Re-export from `domain/__init__.py` (alphabetical + `__all__`).

- [ ] **Step 4:** portfolio tests pass; ruff clean. **Step 5: commit** — `feat(portfolio): relevant project selector`.

---

### Task 3: PortfolioCitationService + provider + bootstrap

**Files:** create `backend/src/hiresense/portfolio/domain/citation_service.py`; modify `domain/__init__.py`, `portfolio/api/provider.py`, `bootstrap/portfolio.py`; tests `backend/tests/unit/portfolio/test_citation_service.py` (+ extend `test_bootstrap.py`)

- [ ] **Step 1: failing test:**

```python
import pytest

from hiresense.portfolio.domain import (
    PortfolioCitationService,
    PortfolioProject,
    ProjectText,
    RelevantProjectSelector,
)


class _FakeRepo:
    def __init__(self, projects):
        self._projects = projects

    def list_all(self):
        return self._projects


def _project(key, tech, *, demo=None):
    return PortfolioProject(
        id=key, source="supabase", source_key=key, tech=tech,
        url=f"https://github.com/x/{key}", demo_url=demo,
        translations={
            "en": ProjectText(title=key.title(), description="Did things."),
            "es": ProjectText(title=f"{key.title()} ES", description="Hizo cosas."),
        },
    )


def _service(projects, *, public_url="https://site.dev", ref_prefix="hiresense"):
    return PortfolioCitationService(
        repository=_FakeRepo(projects),
        selector=RelevantProjectSelector(),
        language="en",
        top_n=2,
        public_url=public_url,
        ref_prefix=ref_prefix,
    )


@pytest.mark.asyncio
async def test_citation_includes_projects_and_tracked_link() -> None:
    service = _service([_project("api", ["fastapi", "python"], demo="https://demo.x")])
    text = await service.citation_for(
        job_skills=["python"], job_text="", application_id="app-1"
    )
    assert text is not None
    assert "Api [fastapi, python]: Did things." in text
    assert "https://github.com/x/api" in text
    assert "https://site.dev/?ref=hiresense-app-1" in text


@pytest.mark.asyncio
async def test_citation_none_when_no_relevant_projects_or_empty_snapshot() -> None:
    service = _service([_project("api", ["fastapi"])])
    assert await service.citation_for(job_skills=["unity"], job_text="", application_id="a") is None
    empty = _service([])
    assert await empty.citation_for(job_skills=["python"], job_text="", application_id="a") is None


@pytest.mark.asyncio
async def test_language_override_and_linkless_mode() -> None:
    service = _service([_project("api", ["python"])], public_url="")
    text = await service.citation_for(
        job_skills=["python"], job_text="", application_id="a", language="es"
    )
    assert text is not None
    assert "Api ES" in text
    assert "?ref=" not in text
```

- [ ] **Step 2:** run → FAIL. **Step 3: implement** `citation_service.py`:

```python
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from hiresense.portfolio.domain.relevant_project_selector import RelevantProjectSelector

if TYPE_CHECKING:
    from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort


class PortfolioCitationService:
    """Builds the optional 'relevant portfolio projects' prompt block for
    generated artifacts (cover letters, outreach), including the
    per-application tracked link. Returns None when there is nothing
    relevant to cite — consumers then behave exactly as before."""

    def __init__(
        self,
        repository: "PortfolioProjectsRepositoryPort",
        selector: RelevantProjectSelector,
        *,
        language: str,
        top_n: int,
        public_url: str,
        ref_prefix: str,
    ) -> None:
        self._repository = repository
        self._selector = selector
        self._language = language
        self._top_n = top_n
        self._public_url = public_url.rstrip("/")
        self._ref_prefix = ref_prefix

    async def citation_for(
        self,
        *,
        job_skills: list[str],
        job_text: str,
        application_id: str,
        language: str | None = None,
    ) -> str | None:
        projects = await asyncio.to_thread(self._repository.list_all)
        if not projects:
            return None
        picked = self._selector.select(
            job_skills=job_skills, job_text=job_text, projects=projects, top_n=self._top_n
        )
        if not picked:
            return None
        lang = language or self._language
        lines = ["Relevant portfolio projects (mention 1-2 naturally where they strengthen the case):"]
        for project in picked:
            text = project.text_for(lang)
            if text is None:
                continue
            line = f"- {text.title}"
            if project.tech:
                line += f" [{', '.join(project.tech)}]"
            first_desc = (text.description or "").strip().splitlines()
            if first_desc and first_desc[0]:
                line += f": {first_desc[0]}"
            links = [link for link in (project.url, project.demo_url) if link]
            if links:
                line += f" ({' | '.join(links)})"
            lines.append(line)
        if len(lines) == 1:
            return None
        if self._public_url:
            lines.append(
                "Include this exact portfolio link once, near the close: "
                f"{self._public_url}/?ref={self._ref_prefix}-{application_id}"
            )
        return "\n".join(lines)
```

Re-export; add `get_citation_service()` to `PortfolioProvider` (constructor gains `citation_service`); in `bootstrap/portfolio.py` build it:

```python
        citation_service=PortfolioCitationService(
            repository=repository,
            selector=RelevantProjectSelector(),
            language=s.default_language,
            top_n=s.portfolio_relevant_projects_top_n,
            public_url=s.portfolio_public_url,
            ref_prefix=s.portfolio_ref_prefix,
        ),
```

Extend `test_bootstrap.py`'s `_Settings` with `portfolio_public_url = ""`, `portfolio_ref_prefix = "hiresense"`, `portfolio_relevant_projects_top_n = 2`, and assert `build.provider.get_citation_service() is not None` in the existing supabase build test.

- [ ] **Step 4:** portfolio tests + full suite pass; ruff clean. **Step 5: commit** — `feat(portfolio): citation service`.

---

### Task 4: Cover letter integration

**Files:** modify `backend/src/hiresense/applications/domain/cover_letter_generator.py`, `applications/domain/apply_service.py`, `bootstrap/applications.py`, `main.py`; test `backend/tests/unit/applications/test_cover_letter_citation.py` (new; study existing tests in `tests/unit/applications/` for the fakes/fixtures already available and reuse them)

- [ ] **Step 1: failing test** (adapt fake names to what exists in `tests/unit/applications/` — the test must cover: (a) generator prompt contains the citation block when provided, (b) ApplyService passes job snapshot skills/description + application_id + cv_language to the citation service, (c) everything unchanged when citation service is None):

```python
import pytest

from hiresense.applications.domain.cover_letter_generator import CoverLetterGenerator


class _FakeLLM:
    def __init__(self):
        self.prompts: list[str] = []

    async def complete(self, prompt: str, system: str | None = None) -> str:
        self.prompts.append(prompt)
        return "letter body"


@pytest.mark.asyncio
async def test_generator_appends_portfolio_section_when_given() -> None:
    llm = _FakeLLM()
    generator = CoverLetterGenerator(llm=llm)
    await generator.generate(
        title="SWE", company="Acme", description="d", candidate_summary="s",
        candidate_skills=["python"], required_skills=["python"], pros=[],
        missing_skills=[], tone="professional",
        portfolio_section="Relevant portfolio projects:\n- Api [python]",
    )
    assert "Relevant portfolio projects:" in llm.prompts[0]
    assert "- Api [python]" in llm.prompts[0]


@pytest.mark.asyncio
async def test_generator_prompt_unchanged_without_portfolio_section() -> None:
    llm = _FakeLLM()
    generator = CoverLetterGenerator(llm=llm)
    await generator.generate(
        title="SWE", company="Acme", description="d", candidate_summary="s",
        candidate_skills=["python"], required_skills=["python"], pros=[],
        missing_skills=[], tone="professional",
    )
    assert "portfolio" not in llm.prompts[0].lower()
```

IMPORTANT: first READ `cover_letter_generator.py` and the existing tests to match the actual `generate(...)` signature/LLM port call — adapt the fake to the real interface (e.g., if the LLM port method is `complete(prompt, system=...)` or different). Keep the two behavioral assertions.

- [ ] **Step 2:** run → FAIL. **Step 3: implement:**
  - `cover_letter_generator.py`: `generate(...)` gains `portfolio_section: str | None = None`. When set, insert into the user prompt BEFORE the "Constraints:" line:

```python
        if portfolio_section:
            prompt += (
                "\n" + portfolio_section + "\n"
                "Weave at most two of these projects into the middle paragraphs "
                "only where they genuinely match the job's needs; if a portfolio "
                "link is given above, include it verbatim exactly once.\n"
            )
```

  (Adapt mechanically to how the prompt string is actually assembled — if it's a single `.format()` template, append the section after formatting, before sending to the LLM, keeping the "Return only the cover letter body." line LAST. Read the file first.)
  - `apply_service.py`: constructor gains `portfolio_citation: Any = None`. In `generate_cover_letter`, after loading `snapshot`:

```python
        portfolio_section = None
        if self._portfolio_citation is not None:
            portfolio_section = await self._portfolio_citation.citation_for(
                job_skills=list(snapshot.required_skills or []),
                job_text=snapshot.description or "",
                application_id=str(application_id),
                language=cv_language,
            )
```

  and pass `portfolio_section=portfolio_section` to the generator.
  - `bootstrap/applications.py`: `build_applications(..., portfolio_citation: Any = None)` → into `ApplyService`.
  - `main.py`: pass `portfolio_citation=portfolio.provider.get_citation_service() if portfolio is not None else None` to `build_applications`.

- [ ] **Step 4:** new tests + FULL suite pass (existing apply-service tests construct ApplyService without the new kwarg — default None keeps them green); ruff clean. **Step 5: commit** — `feat(portfolio): cite relevant projects in cover letters`.

---

### Task 5: Outreach integration

**Files:** modify `backend/src/hiresense/outreach/domain/message_generator.py`, `outreach/domain/outreach_service.py`, `bootstrap/outreach.py`, `main.py`; test `backend/tests/unit/outreach/test_outreach_citation.py` (new; reuse existing outreach test fakes — read `tests/unit/outreach/` first)

- [ ] **Step 1: failing test** — mirrors Task 4: (a) generator appends `portfolio_section` as a conditional part (following the existing `if company_research:` pattern), (b) `OutreachService.generate` calls `citation_for(job_skills=[], job_text=<the job description it already extracts from the tracked app>, application_id=str(application_id))` when the collaborator is set, (c) None ⇒ prompts byte-identical. Write concrete tests after reading the real signatures.

- [ ] **Step 2:** FAIL. **Step 3: implement:**
  - `message_generator.py`: `generate(...)` gains `portfolio_section: str | None = None`; before the final instruction part:

```python
        if portfolio_section:
            parts.append(portfolio_section)
            parts.append(
                "Mention at most ONE of these projects, only if it strengthens the hook; "
                "if a portfolio link is given above, include it verbatim."
            )
```

  - `outreach_service.py`: constructor gains `portfolio_citation: Any = None`; in `generate()`, before calling the generator, compute the section (job_skills=[], job_text = the same job-description string it already passes to the generator, language=self._language) and pass it through.
  - `bootstrap/outreach.py` + `main.py`: same optional-wiring pattern as Task 4.

- [ ] **Step 4:** new tests + FULL suite pass; ruff clean. **Step 5: commit** — `feat(portfolio): cite relevant projects in outreach messages`.

---

### Task 6: Verification + smoke + stacked PR

- [ ] **Step 1:** `uv run python -m pytest -q` (expect ~930+ passed, 0 failed) + `uv run ruff check .`. Frontend untouched.
- [ ] **Step 2: smoke** (compose db up; real `.env`): start app on a free port, login. Pick/create a tracked application with a job snapshot (use existing data if present: `GET /tracking` to find an application id). Generate a cover letter (`POST /applications/{id}/cover-letter` with `{"cv_language": "en", "tone": "professional"}`) → response body should mention a real project (e.g. mesaYA/HireSense-adjacent) AND contain `https://your-portfolio.example.com/?ref=hiresense-<id>` when relevant; if the corpus has no relevant project the section is absent — that's correct behavior, note which case occurred. Same for `POST /outreach/generate`.
- [ ] **Step 3:** push `feat/portfolio-citation`; `gh auth switch --user StevSant`; `gh pr create --base feat/portfolio-github --title "feat(portfolio): cite relevant projects in artifacts (Phase 3)"` with summary (selector + citation service, optional wiring, ref-link format, smoke evidence, note: structured citation display deferred — the letter body shows citations). Claude Code footer.

## Self-review notes (applied)
- Spec coverage: selector, citation in both artifact types, tracked ref link, config — covered. Deferred consciously: storing/displaying structured citations (body text is visible in existing UI); engagement readback is Phase 5.
- Selector keys on terms, not project ids — the id-instability note from Phase 1 doesn't bite here (no persistence of selections).
- Both integrations are optional-collaborator (None default) so every existing test stays green without changes.
