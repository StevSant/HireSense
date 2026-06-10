from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from hiresense.portfolio.domain import PortfolioProject, ProjectText
from hiresense.portfolio.infrastructure.orm import PortfolioProjectOrm


def _to_orm(project: PortfolioProject, synced_at: datetime) -> PortfolioProjectOrm:
    return PortfolioProjectOrm(
        id=project.id,
        source=project.source,
        source_key=project.source_key,
        url=project.url,
        demo_url=project.demo_url,
        pinned=project.pinned,
        position=project.position,
        tech=list(project.tech),
        translations={k: v.model_dump() for k, v in project.translations.items()},
        synced_at=synced_at,
    )


def _to_domain(row: PortfolioProjectOrm) -> PortfolioProject:
    return PortfolioProject(
        id=row.id,
        source=row.source,
        source_key=row.source_key,
        url=row.url,
        demo_url=row.demo_url,
        pinned=row.pinned,
        position=row.position,
        tech=list(row.tech or []),
        translations={k: ProjectText(**v) for k, v in (row.translations or {}).items()},
    )


class PortfolioProjectsRepository:
    """SQL snapshot store; replace_source is atomic per source slice."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def replace_source(self, source: str, projects: list[PortfolioProject]) -> int:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            session.execute(
                delete(PortfolioProjectOrm).where(PortfolioProjectOrm.source == source)
            )
            for project in projects:
                session.add(_to_orm(project, now))
            session.commit()
        return len(projects)

    def list_all(self) -> list[PortfolioProject]:
        with self._session_factory() as session:
            rows = session.scalars(select(PortfolioProjectOrm)).all()
            return [_to_domain(r) for r in rows]

    def last_synced_at(self) -> datetime | None:
        with self._session_factory() as session:
            return session.scalar(select(func.max(PortfolioProjectOrm.synced_at)))
