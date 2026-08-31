from __future__ import annotations

import logging
from typing import Any

from hiresense.runner.browser_driver import BrowserDriver
from hiresense.runner.dom_serializer import serialize_dom

logger = logging.getLogger(__name__)

# How much of the final page to keep as proof of what happened.
EVIDENCE_TEXT_CHARS = 600


class AgentLoop:
    """Drives one submission attempt in the browser.

    Deliberately thin. Every decision -- what to type, whether to submit,
    whether to give up -- is made by the backend; this loop only executes the
    action it is handed and reports what it saw. That keeps the LLM key, the
    candidate's profile, and the grounding rule inside the server.
    """

    def __init__(self, client: Any, driver: BrowserDriver, *, max_steps: int) -> None:
        self._client = client
        self._driver = driver
        self._max_steps = max_steps

    async def run(self, attempt: dict) -> None:
        attempt_id = attempt["id"]
        await self._driver.goto(attempt["target_url"])

        for step in range(self._max_steps):
            observation = serialize_dom(
                await self._driver.html(),
                url=await self._driver.url(),
                title=await self._driver.title(),
            )
            # The serializer only sees serialized HTML. Ask the driver about the
            # places it cannot reach -- shadow roots and cross-origin frames --
            # so a challenge rendered there still stops the run.
            if not observation["captcha_detected"] and await self._challenge_present():
                observation["captcha_detected"] = True
            action = await self._client.observe(attempt_id, observation)
            kind = action.get("kind")

            if kind == "escalate":
                # The server already moved the attempt to `escalated`; the
                # human owns it now.
                logger.info("runner: attempt %s escalated: %s", attempt_id, action.get("reason"))
                return

            if kind == "submit":
                await self._submit(attempt_id, action)
                return

            if kind == "done":
                await self._client.complete(attempt_id, "submitted", action.get("evidence", {}))
                return

            await self._perform(attempt, action)
            await self._client.heartbeat(attempt_id)

        logger.warning("runner: attempt %s hit the %d-step ceiling", attempt_id, self._max_steps)
        await self._client.complete(
            attempt_id,
            "failed",
            {"reason": f"Exceeded the {self._max_steps}-step ceiling without reaching submit"},
        )

    async def _challenge_present(self) -> bool:
        """Driver-side captcha check, tolerant of a driver that lacks it."""
        probe = getattr(self._driver, "challenge_present", None)
        if probe is None:
            return False
        try:
            return bool(await probe())
        except Exception:  # noqa: BLE001 - advisory signal, never fatal
            logger.exception("runner: driver challenge probe failed")
            return False

    async def _perform(self, attempt: dict, action: dict) -> None:
        kind = action.get("kind")
        if kind == "fill_fields":
            for fill in action.get("fills", []):
                await self._driver.fill(fill["selector"], fill["value"])
        elif kind == "click":
            await self._driver.click(action["selector"])
        elif kind == "navigate":
            await self._driver.goto(action["url"])
        elif kind == "upload_file":
            path = await self._client.artifact(attempt["application_id"], action["artifact"])
            if path:
                await self._driver.upload(action["selector"], path)
        else:  # pragma: no cover - the union is closed server-side
            logger.warning("runner: unknown action %r", kind)

    async def _submit(self, attempt_id: str, action: dict) -> None:
        """Click submit -- or, in dry-run, deliberately do not.

        The dry-run branch is the whole safety story of the rollout: everything
        else in the run is identical, so the audit tape a candidate reviews
        before arming the agent is the tape they would have gotten live.
        """
        dry_run = bool(action.get("dry_run", True))
        if not dry_run:
            await self._driver.click(action["selector"])

        evidence = {
            "dry_run": dry_run,
            "final_url": await self._driver.url(),
            "confirmation_text": (await self._driver.text())[:EVIDENCE_TEXT_CHARS],
            "submit_selector": action.get("selector"),
        }
        await self._client.complete(attempt_id, "submitted", evidence)
