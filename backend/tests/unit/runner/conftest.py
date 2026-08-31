"""Opt-in gating for browser-driven runner tests.

Mirrors the `pgvector` pattern in `tests/integration/conftest.py`: tests marked
`playwright` drive a real headless Chromium, so the default
`uv run python -m pytest` run must stay fast and browser-free. They run only
when explicitly selected::

    uv sync --extra agent && uv run playwright install chromium
    uv run python -m pytest -m playwright

Even when selected, they skip gracefully if Playwright or its browser binary is
absent, so `-m playwright` on a machine without them degrades rather than errors.
"""

from __future__ import annotations

import pytest

_MARK = "playwright"


def _selected(config: pytest.Config) -> bool:
    """True when the run explicitly opted in via ``-m playwright``."""
    markexpr = config.getoption("-m", default="") or ""
    return _MARK in markexpr


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _selected(config):
        return
    skip = pytest.mark.skip(
        reason="drives a real browser; opt in with `-m playwright` (needs --extra agent)"
    )
    for item in items:
        if _MARK in item.keywords:
            item.add_marker(skip)
