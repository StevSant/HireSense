from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from hiresense.admin.domain.resolved_config import ResolvedConfig
    from hiresense.admin.domain.test_result import TestResult


class LLMTestRunnerPort(Protocol):
    """Port that validates a ResolvedConfig by issuing a live test call."""

    async def run(self, config: "ResolvedConfig") -> "TestResult": ...
