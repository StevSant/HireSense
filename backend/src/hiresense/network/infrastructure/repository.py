from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from hiresense.network.domain import Contact, normalize_company
from hiresense.network.infrastructure.orm import NetworkContactOrm


def _to_orm(contact: Contact, imported_at: datetime) -> NetworkContactOrm:
    return NetworkContactOrm(
        id=str(uuid.uuid4()),
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        position=contact.position,
        company_normalized=contact.company_normalized,
        linkedin_url=contact.linkedin_url,
        email=contact.email,
        connected_on=contact.connected_on,
        imported_at=imported_at,
    )


def _to_domain(row: NetworkContactOrm) -> Contact:
    return Contact(
        first_name=row.first_name,
        last_name=row.last_name,
        company=row.company,
        position=row.position,
        linkedin_url=row.linkedin_url,
        email=row.email,
        connected_on=row.connected_on,
    )


class ContactsRepository:
    """SQL snapshot store; replace_all is atomic — one full export replaces the previous."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def replace_all(self, contacts: list[Contact]) -> int:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            session.execute(delete(NetworkContactOrm))
            for contact in contacts:
                session.add(_to_orm(contact, now))
            session.commit()
        return len(contacts)

    def list_all(self, company: str | None = None) -> list[Contact]:
        with self._session_factory() as session:
            stmt = select(NetworkContactOrm)
            if company is not None:
                key = normalize_company(company)
                stmt = stmt.where(NetworkContactOrm.company_normalized == key)
            rows = session.scalars(stmt).all()
            return [_to_domain(r) for r in rows]

    def find_by_company(self, company_normalized: str) -> list[Contact]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(NetworkContactOrm).where(
                    NetworkContactOrm.company_normalized == company_normalized
                )
            ).all()
            return [_to_domain(r) for r in rows]

    def count_by_companies(self, companies_normalized: list[str]) -> dict[str, int]:
        if not companies_normalized:
            return {}
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    NetworkContactOrm.company_normalized,
                    func.count(NetworkContactOrm.id),
                )
                .where(NetworkContactOrm.company_normalized.in_(companies_normalized))
                .group_by(NetworkContactOrm.company_normalized)
            ).all()
            return {key: count for key, count in rows}

    def last_imported_at(self) -> datetime | None:
        with self._session_factory() as session:
            return session.scalar(select(func.max(NetworkContactOrm.imported_at)))
