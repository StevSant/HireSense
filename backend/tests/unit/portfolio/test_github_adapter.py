import pytest


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


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


class _FakeHttp:
    def __init__(self, repos, languages_by_repo):
        self._repos = repos
        self._languages = languages_by_repo
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url, headers=None, params=None):
        self.calls.append((url, dict(headers or {})))
        if "/users/" in url:
            return _FakeResponse(self._repos)
        for full_name, langs in self._languages.items():
            if url.endswith(f"/repos/{full_name}/languages"):
                return _FakeResponse(langs)
        raise AssertionError(f"unexpected url {url}")


@pytest.mark.asyncio
async def test_fetch_projects_filters_sorts_and_normalizes() -> None:
    from hiresense.portfolio.adapters import GitHubPortfolioAdapter

    repos = [
        _repo("tiny", stars=1, pushed="2026-02-01T00:00:00Z"),
        _repo("hiresense", stars=5, topics=["FastAPI", "ai"], homepage="https://demo.x"),
        _repo("a-fork", fork=True, stars=99),
        _repo("old", archived=True, stars=99),
    ]
    http = _FakeHttp(repos, {
        "StevSant/hiresense": {"Python": 9000, "TypeScript": 100},
        "StevSant/tiny": {},
    })
    adapter = GitHubPortfolioAdapter(
        http_client=http,
        api_url="https://api.github.com/",
        username="StevSant",
        token="",
        max_repos=30,
    )
    assert adapter.source_name() == "github"
    projects = await adapter.fetch_projects()

    assert [p.source_key for p in projects] == ["StevSant/hiresense", "StevSant/tiny"]
    top = projects[0]
    assert top.position == 0
    assert projects[1].position == 1
    assert top.pinned is False
    assert top.url == "https://github.com/StevSant/hiresense"
    assert top.demo_url == "https://demo.x"
    assert projects[1].demo_url is None  # homepage None -> None
    assert top.tech == ["ai", "fastapi", "python", "typescript"]
    assert top.translations["en"].title == "hiresense"
    assert top.translations["en"].description == "d"
    # No Authorization header without a token; Accept always present
    assert all("Authorization" not in h for _, h in http.calls)
    assert all(h.get("Accept") == "application/vnd.github+json" for _, h in http.calls)


@pytest.mark.asyncio
async def test_equal_stars_ranked_by_recent_push() -> None:
    from hiresense.portfolio.adapters import GitHubPortfolioAdapter

    repos = [
        _repo("older", stars=2, pushed="2026-01-01T00:00:00Z"),
        _repo("newer", stars=2, pushed="2026-03-01T00:00:00Z"),
    ]
    http = _FakeHttp(repos, {"StevSant/older": {}, "StevSant/newer": {}})
    adapter = GitHubPortfolioAdapter(
        http_client=http, api_url="https://api.github.com", username="StevSant",
        token="", max_repos=30,
    )
    projects = await adapter.fetch_projects()
    assert [p.source_key for p in projects] == ["StevSant/newer", "StevSant/older"]


@pytest.mark.asyncio
async def test_max_repos_caps_languages_calls_and_token_header() -> None:
    from hiresense.portfolio.adapters import GitHubPortfolioAdapter

    repos = [_repo("hiresense", stars=5), _repo("tiny", stars=1)]
    http = _FakeHttp(repos, {"StevSant/hiresense": {"Python": 1}})
    adapter = GitHubPortfolioAdapter(
        http_client=http, api_url="https://api.github.com", username="StevSant",
        token="tok", max_repos=1,
    )
    projects = await adapter.fetch_projects()

    assert len(projects) == 1
    language_calls = [u for u, _ in http.calls if u.endswith("/languages")]
    assert language_calls == ["https://api.github.com/repos/StevSant/hiresense/languages"]
    assert all(h.get("Authorization") == "Bearer tok" for _, h in http.calls)


class _PaginatedHttp:
    """Serves repo pages keyed by the ``page=`` query param; /languages -> {}."""

    def __init__(self, pages_by_number):
        self._pages = pages_by_number
        self.repo_list_urls: list[str] = []

    async def get(self, url, headers=None, params=None):
        if "/languages" in url:
            return _FakeResponse({})
        self.repo_list_urls.append(url)
        page = int(url.split("&page=")[1].split("&")[0])
        return _FakeResponse(self._pages.get(page, []))


@pytest.mark.asyncio
async def test_include_private_uses_authenticated_endpoint() -> None:
    from hiresense.portfolio.adapters import GitHubPortfolioAdapter

    http = _PaginatedHttp({1: [_repo("secret")]})
    adapter = GitHubPortfolioAdapter(
        http_client=http, api_url="https://api.github.com", username="ignored",
        token="tok", max_repos=30, include_private=True,
    )
    projects = await adapter.fetch_projects()

    assert [p.source_key for p in projects] == ["StevSant/secret"]
    # Hits /user/repos (authenticated owner) with visibility=all, never /users/<name>.
    assert http.repo_list_urls[0].startswith(
        "https://api.github.com/user/repos?visibility=all&affiliation=owner"
    )
    assert "/users/ignored" not in "".join(http.repo_list_urls)


@pytest.mark.asyncio
async def test_pagination_walks_until_short_page() -> None:
    from hiresense.portfolio.adapters import GitHubPortfolioAdapter

    full_page = [_repo(f"r{i}", pushed=f"2026-01-{i % 28 + 1:02d}T00:00:00Z")
                 for i in range(100)]
    http = _PaginatedHttp({1: full_page, 2: [_repo("last")]})
    adapter = GitHubPortfolioAdapter(
        http_client=http, api_url="https://api.github.com", username="StevSant",
        token="", max_repos=200,
    )
    projects = await adapter.fetch_projects()

    assert len(projects) == 101  # 100 from page 1 + 1 from page 2
    pages = [int(u.split("&page=")[1].split("&")[0]) for u in http.repo_list_urls]
    assert pages == [1, 2]  # stopped once page 2 returned a short page
