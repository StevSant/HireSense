from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from hiresense.network.domain.company_normalization import normalize_company


class Contact(BaseModel):
    """One LinkedIn connection. company_normalized is derived, never set by hand."""

    model_config = ConfigDict(frozen=True)

    first_name: str
    last_name: str
    company: str = ""
    position: str = ""
    linkedin_url: str | None = None
    email: str | None = None
    connected_on: str | None = None
    company_normalized: str = ""

    @model_validator(mode="after")
    def _derive_company_normalized(self) -> "Contact":
        object.__setattr__(self, "company_normalized", normalize_company(self.company))
        return self
