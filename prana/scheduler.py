"""Background scheduler that periodically runs the proactive alert cycle.

Uses a plain asyncio loop (no extra dependency): start it from the FastAPI
lifespan, and it runs run_alert_cycle() every UPDATE_INTERVAL hours until the
app shuts down. The risk function is the same scoring path the agent's
get_risk tool uses, run in a thread so its blocking network calls don't stall
the event loop.
"""
from __future__ import annotations

import asyncio
import logging

from framework.context.user import UserContext
from prana.alerts import run_alert_cycle
from prana.ai_tools.risk import get_risk
from prana.bot.bootstrap import build_messaging, build_repo
from prana.config import UPDATE_INTERVAL

logger = logging.getLogger(__name__)


def _score_user(user: UserContext) -> dict:
    # get_risk is the deterministic scoring path; it hits live weather/AQ APIs.
    return get_risk(ctx=user)


async def _cycle_once() -> int:
    repo = build_repo()
    messaging = build_messaging()
    return await run_alert_cycle(repo, messaging, _score_user)


class AlertScheduler:
    def __init__(self, interval_hours: float = UPDATE_INTERVAL):
        self.interval_seconds = interval_hours * 3600
        self._task: asyncio.Task | None = None

    async def _loop(self) -> None:
        while True:
            try:
                await _cycle_once()
            except Exception:  # noqa: BLE001 - a failed cycle must not kill the loop
                logger.exception("Alert cycle failed")
            await asyncio.sleep(self.interval_seconds)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Alert scheduler started (every %.1f h)", self.interval_seconds / 3600)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("Alert scheduler stopped")
