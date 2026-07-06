from __future__ import annotations

import uuid
from typing import Any

from hiresense.portfolio.domain import PortfolioProject, ProjectText


class SupabasePortfolioAdapter:
    """Reads projects from a Supabase-backed portfolio via PostgREST.

    Relies on the portfolio's public-read RLS for project / project_translation /
    skill_usages / language; the anon key is sufficient.
    """

    def __init__(self, http_client: Any, base_url: str, anon_key: str) -> None:
        self._http = http_client
        self._base = base_url.rstrip("/")
        self._key = anon_key

    def source_name(self) -> str:
        return "supabase"

    async def _get(self, path: str, params: dict[str, str]) -> Any:
        response = await self._http.get(
            f"{self._base}{path}",
            headers={"apikey": self._key, "Authorization": f"Bearer {self._key}"},
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def fetch_projects(self) -> list[PortfolioProject]:
        languages = await self._get("/rest/v1/language", {"select": "id,code"})
        code_by_language_id = {row["id"]: row["code"] for row in languages}

        rows = await self._get(
            "/rest/v1/project",
            {
                "select": "id,code,url,demo_url,is_pinned,position,"
                "project_translation(language_id,title,description)",
                "is_archived": "eq.false",
            },
        )
        usages = await self._get(
            "/rest/v1/skill_usages",
            {
                "select": "source_id,skill(code)",
                "source_type": "eq.project",
                "is_archived": "eq.false",
            },
        )

        tech_by_project: dict[int, list[str]] = {}
        for usage in usages:
            skill = usage.get("skill") or {}
            code = skill.get("code")
            if code:
                tech_by_project.setdefault(usage["source_id"], []).append(code)

        projects: list[PortfolioProject] = []
        for row in rows:
            translations: dict[str, ProjectText] = {}
            for tr in row.get("project_translation") or []:
                code = code_by_language_id.get(tr["language_id"])
                if code:
                    translations[code] = ProjectText(
                        title=tr["title"], description=tr.get("description")
                    )
            if not translations:
                continue  # nothing presentable — skip
            projects.append(
                PortfolioProject(
                    id=str(uuid.uuid4()),
                    source=self.source_name(),
                    source_key=row["code"],
                    url=row.get("url"),
                    demo_url=row.get("demo_url"),
                    pinned=bool(row.get("is_pinned")),
                    position=row.get("position"),
                    tech=sorted(tech_by_project.get(row["id"], [])),
                    translations=translations,
                )
            )
        return projects
