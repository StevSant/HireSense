from __future__ import annotations

import asyncio
import uuid
from typing import Any

from hiresense.portfolio.domain import PortfolioProject, ProjectText


class _ReversedStr(str):
    """Inverts comparison so ISO timestamps sort newest-first inside an
    ascending composite sort key.

    Python's ``sort`` is stable and ascending; negating an integer is the
    natural trick for "largest first", but ISO-8601 strings must be reversed
    by flipping the comparison operators instead.  Subclassing ``str``
    keeps the key a single tuple with no extra dependencies.
    """

    def __lt__(self, other: str) -> bool:  # type: ignore[override]
        return str(self) > str(other)


class GitHubPortfolioAdapter:
    """Reads a user's GitHub repos as portfolio projects.

    By default it lists ``username``'s **public** repos. With
    ``include_private=True`` it instead lists the *token owner's* repos via
    ``GET /user/repos`` (``visibility=all``), which includes private repos —
    this requires a token with the ``repo`` scope and ignores ``username``.

    Forks and archived repos are excluded; repos are ranked by stars then
    most-recent push and capped at ``max_repos`` (each kept repo costs one
    ``/languages`` request).  Results are paginated, so users with more than
    100 repos are fully covered before the cap is applied.
    """

    _PER_PAGE = 100

    def __init__(
        self,
        http_client: Any,
        api_url: str,
        username: str,
        token: str,
        max_repos: int,
        include_private: bool = False,
    ) -> None:
        self._http = http_client
        self._api = api_url.rstrip("/")
        self._username = username
        self._token = token
        self._max_repos = max_repos
        self._include_private = include_private

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

    def _repos_url(self, page: int) -> str:
        common = f"per_page={self._PER_PAGE}&sort=pushed&page={page}"
        if self._include_private:
            # Authenticated endpoint: the token owner's repos, private included.
            return f"{self._api}/user/repos?visibility=all&affiliation=owner&{common}"
        # Public repos of a named user (no private repos, token or not).
        return f"{self._api}/users/{self._username}/repos?type=owner&{common}"

    async def _list_repos(self) -> list[Any]:
        repos: list[Any] = []
        page = 1
        while True:
            batch = await self._get(self._repos_url(page))
            repos.extend(batch)
            if len(batch) < self._PER_PAGE:
                break
            page += 1
        return repos

    async def fetch_projects(self) -> list[PortfolioProject]:
        repos = await self._list_repos()
        kept = [r for r in repos if not r.get("fork") and not r.get("archived")]
        kept.sort(
            key=lambda r: (
                -(r.get("stargazers_count") or 0),
                _ReversedStr(r.get("pushed_at") or ""),
            )
        )
        kept = kept[: self._max_repos]

        # One /languages request per kept repo — issued concurrently so a sync
        # costs one round-trip of latency instead of max_repos sequential ones.
        language_maps = await asyncio.gather(
            *(
                self._get(f"{self._api}/repos/{repo['full_name']}/languages")
                for repo in kept
            )
        )

        projects: list[PortfolioProject] = []
        for index, (repo, languages) in enumerate(zip(kept, language_maps)):
            tech = sorted(
                {language.lower() for language in languages}
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
