from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from hiresense.outreach.domain.email_message import EmailMessage
from hiresense.outreach.domain.outreach_event import OutreachEvent
from hiresense.outreach.domain.outreach_event_kind import OutreachEventKind
from hiresense.outreach.domain.outreach_nudge import OutreachNudge
from hiresense.outreach.domain.recipient_not_allowed_error import RecipientNotAllowedError
from hiresense.outreach.domain.style_guide import load_style_guide

_ACTIVE_STATUSES = {"saved", "applied"}


class OutreachService:
    def __init__(
        self,
        *,
        tracking_service: Any,
        profile_service: Any,
        research_service: Any,
        generator: Any,
        repo: Any,
        style_guide_path: str,
        followup_cadence_days: int,
        max_chars: int,
        language: str,
        portfolio_citation: Any = None,
        sender: Any = None,
        allowed_recipient_domains: tuple[str, ...] = (),
    ) -> None:
        self._sender = sender
        # Lowercased recipient-domain allowlist. Empty = no restriction (any
        # syntactically valid address, still schema-validated as EmailStr).
        self._allowed_recipient_domains = tuple(
            d.strip().lower() for d in allowed_recipient_domains if d.strip()
        )
        self._tracking = tracking_service
        self._profile = profile_service
        self._research = research_service
        self._generator = generator
        self._repo = repo
        self._style_guide_path = style_guide_path
        self._cadence = followup_cadence_days
        self._max_chars = max_chars
        self._language = language
        self._portfolio_citation = portfolio_citation

    async def generate(
        self,
        application_id: uuid.UUID,
        *,
        contact_name: str | None = None,
        channel: str | None = None,
    ) -> str:
        app = self._tracking.get(application_id)  # raises ValueError if missing
        profile = await self._profile.get_current_profile(self._language)
        view = self._profile.get_for_language(self._language)
        research = self._research.get(app.company)
        job_description = getattr(app, "notes", "") or ""
        portfolio_section = None
        if self._portfolio_citation is not None:
            portfolio_section = await self._portfolio_citation.citation_for(
                job_skills=[],
                job_text=job_description,
                application_id=str(application_id),
                language=self._language,
            )
        return await self._generator.generate(
            company=app.company,
            title=getattr(app, "title", ""),
            job_description=job_description,
            candidate_name=(profile.name if profile is not None else ""),
            candidate_summary=(view.summary if view is not None else ""),
            candidate_skills=(list(view.skills) if view is not None else []),
            company_research=self._research_blurb(research),
            contact_name=contact_name,
            style_guide=load_style_guide(self._style_guide_path),
            channel=channel,
            max_chars=self._max_chars,
            portfolio_section=portfolio_section,
        )

    def record(
        self,
        application_id: uuid.UUID,
        *,
        kind: OutreachEventKind,
        message: str | None = None,
        contact_name: str | None = None,
        channel: str | None = None,
    ) -> OutreachEvent:
        self._tracking.get(application_id)  # 404 if missing
        return self._repo.add(
            OutreachEvent(
                application_id=application_id,
                kind=kind,
                message=message,
                contact_name=contact_name,
                channel=channel,
            )
        )

    async def send(
        self,
        application_id: uuid.UUID,
        *,
        to: str,
        subject: str,
        message: str,
        contact_name: str | None = None,
        channel: str = "email",
    ) -> OutreachEvent:
        """Send an outreach email, then record it as a SENT event.

        Raises ValueError if the application is missing, RecipientNotAllowedError
        if the recipient domain is outside the configured allowlist, and
        EmailUnavailableError (from the sender) if SMTP isn't configured —
        nothing is recorded when the send fails.
        """
        self._tracking.get(application_id)  # 404 if missing
        self._ensure_recipient_allowed(to)
        await asyncio.to_thread(
            self._sender.send, EmailMessage(to=to, subject=subject, body=message)
        )
        return self._repo.add(
            OutreachEvent(
                application_id=application_id,
                kind=OutreachEventKind.SENT,
                message=message,
                contact_name=contact_name,
                channel=channel,
            )
        )

    def _ensure_recipient_allowed(self, to: str) -> None:
        if not self._allowed_recipient_domains:
            return
        domain = to.rsplit("@", 1)[-1].strip().lower()
        if domain not in self._allowed_recipient_domains:
            raise RecipientNotAllowedError(
                f"Recipient domain '{domain}' is not in the outreach allowlist"
            )

    def list_for(self, application_id: uuid.UUID) -> list[OutreachEvent]:
        return self._repo.list_for(application_id)

    def due_followups(self) -> list[OutreachNudge]:
        now = datetime.now(timezone.utc)
        nudges: list[OutreachNudge] = []
        for latest in self._repo.latest_per_application():
            if latest.kind != OutreachEventKind.SENT or latest.created_at is None:
                continue
            sent_at = latest.created_at
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            # .days floors the delta to whole days elapsed, so a follow-up is due
            # only after a full `cadence` × 24h has passed (intentional).
            days_since = (now - sent_at).days
            if days_since < self._cadence:
                continue
            try:
                app = self._tracking.get(latest.application_id)
            except ValueError:
                continue  # application deleted — skip
            if app.status not in _ACTIVE_STATUSES:
                continue
            nudges.append(
                OutreachNudge(
                    application_id=latest.application_id,
                    company=app.company,
                    contact_name=latest.contact_name,
                    sent_at=sent_at,
                    days_since=days_since,
                )
            )
        return nudges

    @staticmethod
    def _research_blurb(research: Any | None) -> str | None:
        if research is None:
            return None
        bits = []
        for label, attr in (
            ("Culture", "culture_summary"),
            ("Tech", "tech_stack"),
            ("Pros", "pros"),
        ):
            value = getattr(research, attr, None)
            if value:
                bits.append(f"{label}: {value}")
        return " | ".join(bits) or None
