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
        self.calls.append((url, dict(params or {})))
        for path, payload in self._payloads.items():
            if path in url:
                return _FakeResponse(payload)
        raise AssertionError(f"unexpected url {url}")


_PAYLOADS = {
    "/rest/v1/language": [{"id": 1, "code": "en"}, {"id": 2, "code": "es"}],
    "/rest/v1/project": [
        {
            "id": 10,
            "code": "hiresense",
            "url": "https://github.com/x/hiresense",
            "demo_url": None,
            "is_pinned": True,
            "position": 1,
            "project_translation": [
                {"language_id": 1, "title": "HireSense", "description": "AI job hunting"},
                {"language_id": 2, "title": "HireSense ES", "description": "Caza de empleo"},
            ],
        },
        {
            "id": 11,
            "code": "untranslated",
            "url": None,
            "demo_url": None,
            "is_pinned": False,
            "position": None,
            "project_translation": [],
        },
    ],
    "/rest/v1/skill_usages": [
        {"source_id": 10, "skill": {"code": "python"}},
        {"source_id": 10, "skill": {"code": "angular"}},
        {"source_id": 99, "skill": {"code": "elsewhere"}},
        {"source_id": 10, "skill": None},
    ],
}


@pytest.mark.asyncio
async def test_fetch_projects_normalizes_translations_and_tech() -> None:
    from hiresense.portfolio.adapters import SupabasePortfolioAdapter

    http = _FakeHttp(_PAYLOADS)
    adapter = SupabasePortfolioAdapter(
        http_client=http, base_url="https://xyz.supabase.co", anon_key="anon"
    )
    assert adapter.source_name() == "supabase"
    projects = await adapter.fetch_projects()

    assert len(projects) == 1  # untranslated project is dropped
    project = projects[0]
    assert project.source == "supabase"
    assert project.source_key == "hiresense"
    assert project.pinned is True
    assert project.tech == ["angular", "python"]
    assert project.translations["es"].title == "HireSense ES"


@pytest.mark.asyncio
async def test_fetch_projects_sends_auth_headers_and_filters() -> None:
    from hiresense.portfolio.adapters import SupabasePortfolioAdapter

    captured_headers = {}

    class _Http(_FakeHttp):
        async def get(self, url, headers=None, params=None):
            captured_headers.update(headers or {})
            return await super().get(url, headers=headers, params=params)

    http = _Http(_PAYLOADS)
    adapter = SupabasePortfolioAdapter(
        http_client=http, base_url="https://xyz.supabase.co", anon_key="anon"
    )
    await adapter.fetch_projects()

    assert captured_headers["apikey"] == "anon"
    assert captured_headers["Authorization"] == "Bearer anon"
    project_call = next(c for c in http.calls if "/rest/v1/project" in c[0])
    assert project_call[1]["is_archived"] == "eq.false"
