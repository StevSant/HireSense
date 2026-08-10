from __future__ import annotations

from pydantic import BaseModel


class TexDiffDTO(BaseModel):
    optimization_id: str
    original_path: str
    diff: str
    modified_tex: str
