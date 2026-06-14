from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from hiresense.infrastructure import SqlRepository
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


class PortfolioProjectsRepository(SqlRepository):
    """SQL snapshot store; replace_source is atomic per source slice."""

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
        return self._select_all(select(PortfolioProjectOrm), _to_domain)

    def list_page(self, limit: int, offset: int) -> tuple[list[PortfolioProject], int]:
        stmt = (
            select(PortfolioProjectOrm)
            .order_by(
                PortfolioProjectOrm.pinned.desc(),
                # position NULLs last (False sorts before True), then ascending.
                PortfolioProjectOrm.position.is_(None),
                PortfolioProjectOrm.position.asc(),
                PortfolioProjectOrm.source_key.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        with self._session_factory() as session:
            rows = [_to_domain(r) for r in session.scalars(stmt).all()]
            total = session.scalar(
                select(func.count()).select_from(PortfolioProjectOrm)
            )
        return rows, int(total or 0)

    def last_synced_at(self) -> datetime | None:
        with self._session_factory() as session:
            return session.scalar(select(func.max(PortfolioProjectOrm.synced_at)))
