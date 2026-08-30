from __future__ import annotations

from pydantic import BaseModel, Field


class FormField(BaseModel):
    """One input on an application form, as the runner observed it."""

    selector: str
    label: str
    field_type: str
    required: bool = False
    options: list[str] = Field(default_factory=list)
    current_value: str | None = None

    @property
    def is_filled(self) -> bool:
        return bool((self.current_value or "").strip())
