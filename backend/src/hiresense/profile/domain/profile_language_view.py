from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileLanguageView:
    language: str
    summary: str
    skills: list[str]
    raw_tex: str
