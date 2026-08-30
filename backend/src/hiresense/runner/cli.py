from __future__ import annotations

import asyncio
import logging
import socket
import sys

from dotenv import load_dotenv

logger = logging.getLogger("hiresense.runner")


async def _drain() -> int:
    from hiresense.runner.agent_loop import AgentLoop
    from hiresense.runner.client import SubmissionClient
    from hiresense.runner.playwright_driver import PlaywrightDriver
    from hiresense.shared.config import Settings

    settings = Settings()
    runner_id = f"{socket.gethostname()}-{__name__}"[:64]

    client = SubmissionClient(
        settings.apply_agent_api_base,
        settings.apply_agent_api_token.get_secret_value(),
    )
    try:
        attempts = await client.lease(runner_id, capacity=1)
        if not attempts:
            logger.info("runner: nothing queued")
            return 0

        driver = PlaywrightDriver(settings.apply_agent_cdp_url)
        await driver.start()
        try:
            loop = AgentLoop(client, driver, max_steps=settings.apply_agent_max_steps)
            for attempt in attempts:
                logger.info(
                    "runner: starting attempt %s -> %s (dry_run=%s)",
                    attempt["id"],
                    attempt["target_url"],
                    settings.apply_agent_dry_run,
                )
                await loop.run(attempt)
        finally:
            await driver.close()
        return len(attempts)
    finally:
        await client.aclose()


def main() -> None:
    """Entry point for `uv run apply-agent`.

    Leases queued submissions and drives them in the candidate's own Chrome.
    Chrome must be started with --remote-debugging-port matching
    APPLY_AGENT_CDP_URL.
    """
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        processed = asyncio.run(_drain())
    except Exception:  # noqa: BLE001 - report cleanly rather than dumping a trace
        logger.exception("runner: run failed")
        sys.exit(1)
    logger.info("runner: processed %d attempt(s)", processed)
