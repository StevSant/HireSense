from __future__ import annotations

from typing import Protocol

from hiresense.research.domain.firmographics import Firmographics


class FirmographicsPort(Protocol):
    async def fetch(self, company_name: str) -> Firmographics | None: ...
