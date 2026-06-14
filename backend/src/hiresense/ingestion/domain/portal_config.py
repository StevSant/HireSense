from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class PortalEntry(BaseModel):
    name: str
    platform: Literal[
        "greenhouse", "lever", "ashby", "workable", "smartrecruiters", "recruitee"
    ]
    board_id: str
    categories: list[str] = []
    enabled: bool = True


class PortalsConfig(BaseModel):
    portals: list[PortalEntry]


def load_portals_config(path: Path) -> PortalsConfig:
    """Load and validate portals.yml from the given path."""
    if not path.exists():
        raise FileNotFoundError(f"Portals config not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PortalsConfig.model_validate(data)
