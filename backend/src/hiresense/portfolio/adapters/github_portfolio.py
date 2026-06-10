from __future__ import annotations

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
    """Reads a user's public GitHub repos as portfolio projects.

    Forks and archived repos are excluded; repos are ranked by stars then
    most-recent push and capped at ``max_repos`` (each kept repo costs one
    ``/languages`` request).  A token is optional — it raises the rate limit
    and includes private repos.
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
        kept.sort(
            key=lambda r: (
                -(r.get("stargazers_count") or 0),
                _ReversedStr(r.get("pushed_at") or ""),
            )
        )
        kept = kept[: self._max_repos]

        projects: list[PortfolioProject] = []
        for index, repo in enumerate(kept):
            languages = await self._get(
                f"{self._api}/repos/{repo['full_name']}/languages"
            )
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
