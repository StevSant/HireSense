from __future__ import annotations

from typing import Any, Callable, TypeVar

from sqlalchemy import Select

RowT = TypeVar("RowT")
DomainT = TypeVar("DomainT")


class SqlRepository:
    """Shared plumbing for the sync SQLAlchemy repositories.

    Owns the session factory and the recurring CRUD shapes: insert-and-map,
    get-by-pk, select one/many, update-by-pk, delete-by-pk. Each helper takes
    the ORM->domain mapper explicitly so repositories that span several ORM
    classes reuse the same plumbing. Bespoke queries keep using
    ``self._session_factory`` directly.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def _insert(self, row: RowT, map_row: Callable[[RowT], DomainT]) -> DomainT:
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return map_row(row)

    def _get_by_pk(
        self, orm_cls: type[RowT], pk: Any, map_row: Callable[[RowT], DomainT]
    ) -> DomainT | None:
        with self._session_factory() as session:
            row = session.get(orm_cls, pk)
            return map_row(row) if row is not None else None

    def _select_one(
        self, stmt: Select[Any], map_row: Callable[[Any], DomainT]
    ) -> DomainT | None:
        with self._session_factory() as session:
            row = session.scalars(stmt).first()
            return map_row(row) if row is not None else None

    def _select_all(
        self, stmt: Select[Any], map_row: Callable[[Any], DomainT]
    ) -> list[DomainT]:
        with self._session_factory() as session:
            return [map_row(r) for r in session.scalars(stmt).all()]

    def _update_by_pk(
        self,
        orm_cls: type[RowT],
        pk: Any,
        fields: dict[str, Any],
        map_row: Callable[[RowT], DomainT],
    ) -> DomainT | None:
        with self._session_factory() as session:
            row = session.get(orm_cls, pk)
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return map_row(row)

    def _delete_by_pk(self, orm_cls: type[Any], pk: Any) -> bool:
        with self._session_factory() as session:
            row = session.get(orm_cls, pk)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
