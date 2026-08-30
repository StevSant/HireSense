from __future__ import annotations

from typing import Protocol


class AnswerBankPort(Protocol):
    """Persists answers a human supplied so the agent never has to ask twice.

    The learning loop's write side. Without it the confidence gate is a
    permanent bottleneck; with it, the escalation queue drains toward empty as
    the candidate's answer corpus fills in.
    """

    async def remember(self, answers: list[tuple[str, str]]) -> None: ...
