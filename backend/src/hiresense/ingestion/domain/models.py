from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RawJobListing(BaseModel):
    source: str
    source_id: str
    raw_data: dict[str, Any]
