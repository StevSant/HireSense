from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class JobId:
    _value: str

    @classmethod
    def generate(cls) -> JobId:
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JobId):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


@dataclass(frozen=True)
class SkillTag:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", self.value.strip().lower())


@dataclass(frozen=True)
class Score:
    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", max(0, min(100, self.value)))


@dataclass(frozen=True)
class MatchScore:
    semantic: int
    skill_match: int
    experience: int
    language: int

    def composite(
        self,
        w_semantic: int,
        w_skill: int,
        w_exp: int,
        w_lang: int,
    ) -> float:
        total = (
            self.semantic * w_semantic
            + self.skill_match * w_skill
            + self.experience * w_exp
            + self.language * w_lang
        )
        return total / (w_semantic + w_skill + w_exp + w_lang)


class Language(Enum):
    ENGLISH = "en"
    SPANISH = "es"


class SourceType(Enum):
    API = "api"
    RSS = "rss"
    SCRAPER = "scraper"
    MANUAL = "manual"
