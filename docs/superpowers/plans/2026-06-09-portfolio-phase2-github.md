# Portfolio Phase 2 (GitHub adapter) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GitHubPortfolioAdapter` — second `PortfolioSourcePort` implementation, validating the port: public GitHub repos become `PortfolioProject`s feeding the same sync/enrichment pipeline.

**Architecture:** One new adapter in `portfolio/adapters/` + a `github` branch in `bootstrap/portfolio.py` + four config keys. No domain, port, repository, API, or frontend changes — that's the point of the port. Spec: `docs/superpowers/specs/2026-06-09-external-sources-integration-design.md` (Part A, rollout phase 2).

**Tech Stack:** GitHub REST API v3 (`/users/{u}/repos`, `/repos/{o}/{r}/languages`), optional PAT.

**Working directory:** `C:\Users\Bryan\worktrees\hiresense-portfolio` (branch `feat/portfolio-github`, stacked on `feat/portfolio-integration`; the PR's base is that branch, NOT main). Backend commands from `backend/`. **Windows quirk:** always `uv run python -m pytest` (never bare `uv run pytest`). No repo-wide `ruff format`.

**GitHub API facts the implementer needs:**
- `GET {api}/users/{username}/repos?per_page=100&type=owner&sort=pushed` returns repos including `name`, `full_name`, `description`, `html_url`, `homepage`, `fork`, `archived`, `stargazers_count`, `pushed_at`, `topics` (topics included by default on current API versions).
- `GET {api}/repos/{full_name}/languages` returns `{"Python": 31415, "TypeScript": 271}` (bytes).
- Headers: `Accept: application/vnd.github+json`; when a token is configured also `Authorization: Bearer <token>` (raises rate limit 60→5000/h and includes private repos).
- Mapping decided in the spec + here: exclude forks and archived; `source_key=full_name`; `url=html_url`; `demo_url=homepage or None` (empty string → None); `pinned=False` (REST can't see pinned repos); order by `(-stargazers_count, pushed_at desc)` → `position=index`; `tech` = top languages by bytes + topics, lowercased, deduped, sorted; translations: `{"en": ProjectText(title=name, description=description)}`. Repos with no description still count (description None). Cap the number of repos AFTER sorting via `portfolio_github_max_repos` (bounds the per-repo languages calls; one languages call per kept repo).

---

### Task 1: Config + env files

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `backend/.env`, `backend/.env.example`
- Test: `backend/tests/unit/test_config.py`

- [ ] **Step 1: failing test** — append to `backend/tests/unit/test_config.py`:

```python
def test_portfolio_github_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    # Pin against whatever the local backend/.env contains (env > dotenv).
    monkeypatch.setenv("PORTFOLIO_GITHUB_USERNAME", "")
    monkeypatch.setenv("PORTFOLIO_GITHUB_TOKEN", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.portfolio_github_username == ""
    assert settings.portfolio_github_token == ""
    assert settings.portfolio_github_api_url == "https://api.github.com"
    assert settings.portfolio_github_max_repos == 30
```

- [ ] **Step 2:** `uv run python -m pytest tests/unit/test_config.py -q` → new test FAILS.

- [ ] **Step 3: implement** — in `config.py`, extend the existing `# --- Portfolio ... ---` block (after `portfolio_supabase_anon_key`):

```python
    # GitHub source adapter: public repos of this user become portfolio
    # projects. Token is optional (rate limit 60 -> 5000 req/h; includes
    # private repos when set).
    portfolio_github_username: str = ""
    portfolio_github_token: str = ""
    portfolio_github_api_url: str = "https://api.github.com"
    # Repos kept after sorting by stars + recent push. Bounds the per-repo
    # languages calls (one HTTP request per kept repo).
    portfolio_github_max_repos: int = 30
```

- [ ] **Step 4:** test passes; whole `tests/unit/test_config.py` green.

- [ ] **Step 5: env files.** `backend/.env.example` — extend the portfolio section:

```
# GitHub source adapter (optional). Token raises rate limits / adds private repos.
PORTFOLIO_GITHUB_USERNAME=
PORTFOLIO_GITHUB_TOKEN=
PORTFOLIO_GITHUB_API_URL=https://api.github.com
PORTFOLIO_GITHUB_MAX_REPOS=30
```

`backend/.env` (gitignored): same block with `PORTFOLIO_GITHUB_USERNAME=StevSant`, token empty, and change `PORTFOLIO_SOURCES=supabase` → `PORTFOLIO_SOURCES=supabase,github`.

- [ ] **Step 6: commit** — `feat(portfolio): github source settings` (config.py, .env.example, test_config.py; body trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`).

---

### Task 2: GitHubPortfolioAdapter

**Files:**
- Create: `backend/src/hiresense/portfolio/adapters/github_portfolio.py`
- Modify: `backend/src/hiresense/portfolio/adapters/__init__.py`
- Test: `backend/tests/unit/portfolio/test_github_adapter.py`

- [ ] **Step 1: failing test:**

```python
import pytest


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, payload_by_path: dict):
        self._payloads = payload_by_path
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url, headers=None, params=None):
        self.calls.append((url, dict(headers or {})))
        for path, payload in self._payloads.items():
            if url.endswith(path):
                return _FakeResponse(payload)
        raise AssertionError(f"unexpected url {url}")


def _repo(name, *, stars=0, fork=False, archived=False, topics=None, description="d",
          homepage=None, pushed="2026-01-01T00:00:00Z"):
    return {
        "name": name,
        "full_name": f"StevSant/{name}",
        "description": description,
        "html_url": f"https://github.com/StevSant/{name}",
        "homepage": homepage,
        "fork": fork,
        "archived": archived,
        "stargazers_count": stars,
        "pushed_at": pushed,
        "topics": topics or [],
    }


_PAYLOADS = {
    "/users/StevSant/repos?per_page=100&type=owner&sort=pushed": None,  # replaced below
    "/repos/StevSant/hiresense/languages": {"Python": 9000, "TypeScript": 100},
    "/repos/StevSant/tiny/languages": {},
}


@pytest.mark.asyncio
async def test_fetch_projects_filters_sorts_and_normalizes() -> None:
    from hiresense.portfolio.adapters import GitHubPortfolioAdapter

    repos = [
        _repo("tiny", stars=1, pushed="2026-02-01T00:00:00Z"),
        _repo("hiresense", stars=5, topics=["FastAPI", "ai"], homepage="https://demo.x"),
        _repo("a-fork", fork=True),
        _repo("old", archived=True),
    ]
    payloads = dict(_PAYLOADS)
    payloads["/users/StevSant/repos?per_page=100&type=owner&sort=pushed"] = repos

    class _Http(_FakeHttp):
        async def get(self, url, headers=None, params=None):
            # repo listing is requested with params, languages without
            if "/users/" in url:
                return _FakeResponse(repos)
            return await super().get(url, headers=headers, params=params)

    adapter = GitHubPortfolioAdapter(
        http_client=_Http(payloads),
        api_url="https://api.github.com",
        username="StevSant",
        token="",
        max_repos=30,
    )
    assert adapter.source_name() == "github"
    projects = await adapter.fetch_projects()

    assert [p.source_key for p in projects] == ["StevSant/hiresense", "StevSant/tiny"]
    top = projects[0]
    assert top.position == 0
    assert top.pinned is False
    assert top.url == "https://github.com/StevSant/hiresense"
    assert top.demo_url == "https://demo.x"
    assert top.tech == ["ai", "fastapi", "python", "typescript"]
    assert top.translations["en"].title == "hiresense"
    assert top.translations["en"].description == "d"


@pytest.mark.asyncio
async def test_max_repos_caps_languages_calls_and_token_header() -> None:
    from hiresense.portfolio.adapters import GitHubPortfolioAdapter

    repos = [
        _repo("hiresense", stars=5),
        _repo("tiny", stars=1),
    ]

    captured: list[tuple[str, dict]] = []

    class _Http:
        async def get(self, url, headers=None, params=None):
            captured.append((url, dict(headers or {})))
            if "/users/" in url:
                return _FakeResponse(repos)
            return _FakeResponse({"Python": 1})

    adapter = GitHubPortfolioAdapter(
        http_client=_Http(),
        api_url="https://api.github.com",
        username="StevSant",
        token="tok",
        max_repos=1,
    )
    projects = await adapter.fetch_projects()

    assert len(projects) == 1  # capped after sorting: only the starred repo kept
    language_calls = [u for u, _ in captured if u.endswith("/languages")]
    assert language_calls == ["https://api.github.com/repos/StevSant/hiresense/languages"]
    assert all(h.get("Authorization") == "Bearer tok" for _, h in captured)
    assert all(h.get("Accept") == "application/vnd.github+json" for _, h in captured)
```

- [ ] **Step 2:** `uv run python -m pytest tests/unit/portfolio/test_github_adapter.py -q` → FAIL.

- [ ] **Step 3: implement** `backend/src/hiresense/portfolio/adapters/github_portfolio.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from hiresense.portfolio.domain import PortfolioProject, ProjectText


class GitHubPortfolioAdapter:
    """Reads a user's public GitHub repos as portfolio projects.

    Forks and archived repos are excluded; repos are ranked by stars then
    recent push and capped at `max_repos` (each kept repo costs one extra
    /languages request). A token is optional — it raises the rate limit and
    includes private repos.
    """

    def __init__(
        self,
        http_client: Any,
        api_url: str,
        username: str,
        token: str,
        max_repos: int,
    ) -> None:
        self._http = http_client
        self._api = api_url.rstrip("/")
        self._username = username
        self._token = token
        self._max_repos = max_repos

    def source_name(self) -> str:
        return "github"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _get(self, url: str) -> Any:
        response = await self._http.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    async def fetch_projects(self) -> list[PortfolioProject]:
        repos = await self._get(
            f"{self._api}/users/{self._username}/repos?per_page=100&type=owner&sort=pushed"
        )
        kept = [r for r in repos if not r.get("fork") and not r.get("archived")]
        kept.sort(key=lambda r: (-r.get("stargazers_count", 0), r.get("pushed_at") or ""), reverse=False)
        # Stars descending is handled by the negative key; for equal stars the
        # most recently pushed repo should come first:
        kept.sort(key=lambda r: (-(r.get("stargazers_count") or 0), _desc(r.get("pushed_at") or "")))
        kept = kept[: self._max_repos]

        projects: list[PortfolioProject] = []
        for index, repo in enumerate(kept):
            languages = await self._get(f"{self._api}/repos/{repo['full_name']}/languages")
            tech = sorted(
                {lang.lower() for lang in languages}
                | {topic.lower() for topic in repo.get("topics") or []}
            )
            projects.append(
                PortfolioProject(
                    id=str(uuid.uuid4()),
                    source=self.source_name(),
                    source_key=repo["full_name"],
                    url=repo.get("html_url"),
                    demo_url=repo.get("homepage") or None,
                    pinned=False,
                    position=index,
                    tech=tech,
                    translations={
                        "en": ProjectText(
                            title=repo["name"], description=repo.get("description")
                        )
                    },
                )
            )
        return projects


class _desc(str):
    """Inverts string comparison so ISO timestamps sort newest-first inside an
    ascending composite sort key."""

    def __lt__(self, other: str) -> bool:  # type: ignore[override]
        return str(self) > str(other)
```

NOTE to implementer: the double-sort above is redundant — implement ONE clean ordering: stars descending, then `pushed_at` descending. The `_desc` helper achieves that in a single `sort(key=lambda r: (-(stars), _desc(pushed_at)))`. Delete the first redundant `kept.sort(...)` line; it's shown only to explain intent. `_desc` lives in the same file (private helper, allowed alongside the one public class).

Update `backend/src/hiresense/portfolio/adapters/__init__.py`:

```python
from hiresense.portfolio.adapters.github_portfolio import GitHubPortfolioAdapter
from hiresense.portfolio.adapters.supabase_portfolio import SupabasePortfolioAdapter

__all__ = ["GitHubPortfolioAdapter", "SupabasePortfolioAdapter"]
```

- [ ] **Step 4:** `uv run python -m pytest tests/unit/portfolio -q` → all PASS; `uv run ruff check src/hiresense/portfolio tests/unit/portfolio` clean.

- [ ] **Step 5: commit** — `feat(portfolio): GitHub source adapter` (+ trailer).

---

### Task 3: Bootstrap wiring

**Files:**
- Modify: `backend/src/hiresense/bootstrap/portfolio.py`
- Test: `backend/tests/unit/portfolio/test_bootstrap.py`

- [ ] **Step 1: failing tests** — append to `test_bootstrap.py` (extend `_Settings` with the new attrs first):

Add to `_Settings`:

```python
    portfolio_github_username = ""
    portfolio_github_token = ""
    portfolio_github_api_url = "https://api.github.com"
    portfolio_github_max_repos = 30
```

New tests:

```python
def test_raises_when_github_enabled_without_username() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["github"]
    with pytest.raises(ValueError, match="PORTFOLIO_GITHUB_USERNAME"):
        build_portfolio(_Infra(settings))


def test_builds_provider_with_github_and_supabase() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase", "github"]
    settings.portfolio_supabase_url = "https://xyz.supabase.co"
    settings.portfolio_supabase_anon_key = "anon"
    settings.portfolio_github_username = "StevSant"
    build = build_portfolio(_Infra(settings))
    assert build is not None
```

- [ ] **Step 2:** run → FAIL (ValueError not raised / unknown source "github").

- [ ] **Step 3: implement** — in `bootstrap/portfolio.py`, import `GitHubPortfolioAdapter` from `hiresense.portfolio.adapters` and add before the `else`:

```python
        elif name == "github":
            if not s.portfolio_github_username:
                raise ValueError(
                    "portfolio source 'github' is enabled but "
                    "PORTFOLIO_GITHUB_USERNAME is not set"
                )
            sources.append(
                GitHubPortfolioAdapter(
                    http_client=infra.http_client,
                    api_url=s.portfolio_github_api_url,
                    username=s.portfolio_github_username,
                    token=s.portfolio_github_token,
                    max_repos=s.portfolio_github_max_repos,
                )
            )
```

- [ ] **Step 4:** `uv run python -m pytest tests/unit/portfolio -q` → all PASS; full suite `uv run python -m pytest -q` → all PASS; ruff clean.

- [ ] **Step 5: commit** — `feat(portfolio): wire github source in bootstrap` (+ trailer).

---

### Task 4: Verification + live smoke + stacked PR

- [ ] **Step 1:** from `backend/`: `uv run python -m pytest -q` (expect 920+ passed) and `uv run ruff check .` clean. Frontend untouched — CI covers it.

- [ ] **Step 2: live smoke.** Ensure `backend/.env` has `PORTFOLIO_SOURCES=supabase,github` + `PORTFOLIO_GITHUB_USERNAME=StevSant`. Start the app on a free port, login (AUTH_PASSWORD from `backend/.env`), then:
  - `POST /portfolio/sync` → expect `counts_by_source` with BOTH `supabase` (17) and `github` (>0), `errors: {}`.
  - `GET /portfolio/projects` → projects from both sources present (`source` field distinguishes them); GitHub entries have lowercase tech from languages+topics.

- [ ] **Step 3: push + stacked PR** (gh account flips — switch first):

```bash
git push -u origin feat/portfolio-github
gh auth switch --user StevSant
gh pr create --base feat/portfolio-integration --title "feat(portfolio): GitHub source adapter (Phase 2)" --body "..."
```

PR body: second `PortfolioSourcePort` implementation validating the port; mapping decisions (forks/archived excluded, stars+push ordering, languages+topics → tech, max-repos cap); smoke evidence; note base branch is Phase 1. End with the Claude Code footer.

---

## Self-review notes (applied)

- Spec coverage: Part A GitHub adapter fully covered; no Phase 3+ creep (no selector, no ref links).
- Type consistency: adapter constructor matches bootstrap call; `source_name() == "github"` matches `PORTFOLIO_SOURCES` token and the ORM `source` column.
- The `_desc` sort helper is the one intentional non-trivial bit; tests pin the ordering.
