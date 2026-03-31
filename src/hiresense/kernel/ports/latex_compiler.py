from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CompilationError:
    line: int
    message: str


class LaTeXCompilerPort(Protocol):
    async def compile(self, tex_content: str) -> bytes: ...

    async def validate(self, tex_content: str) -> list[CompilationError]: ...
