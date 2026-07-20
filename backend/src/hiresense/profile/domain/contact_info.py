from __future__ import annotations

from pydantic import BaseModel


class ContactInfo(BaseModel):
    """Letterhead contact details for the candidate — the public projection of
    a stored profile's name/email/phone, exposed so consumers (e.g. cover-letter
    rendering) never reach into ``ProfileService`` internals to read them.
    """

    name: str | None = None
    email: str | None = None
    phone: str | None = None
