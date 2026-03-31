from __future__ import annotations

from typing import Any, Protocol

from fastapi import FastAPI


class Module(Protocol):
    def register(self, app: FastAPI, dependencies: dict[str, Any]) -> None: ...
