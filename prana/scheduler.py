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

from prana.alerts import run_alert_cycle
from prana.ai_tools.risk import get_risk
from prana.bot.bootstrap import (
    build_messaging, build_repo, build_checkin_repo, build_rds_repo,
)
from prana.config import UPDATE_INTERVAL, RDS_NIGHTTIME_THRESHOLD
from prana.personalization import personalize_offset
from prana.rds_calculator import RDSCalculator
from prana.prana_system import PRANASystem

logger = logging.getLogger(__name__)


async def _cycle_once() -> int:
    repo = build_repo()
    messaging = build_messaging()
    rds_repo = build_rds_repo()
    checkin_repo = build_checkin_repo()

    async def score(user):
        historical_temps = await rds_repo.load(user.user_id)
        personalization = None
        checkins = await checkin_repo.list_for_user(user.user_id, limit=30)
        if checkins:
            onb = user.metadata.get("onboarding") or {}
            dummy = PRANASystem(location_name=user.metadata.get("location_name") or "default")
            prior_mean = RDSCalculator.compute_onboarding_temp_offset(
                onb, climate_zone=dummy.climate_zone
            )
            prior_sd = RDSCalculator.compute_band_width(onb)
            post = personalize_offset(prior_mean, prior_sd, checkins, RDS_NIGHTTIME_THRESHOLD)
            personalization = {
                "offset": post.mean,
                "band": post.sd,
                "n_checkins": post.n_checkins,
            }
        return await get_risk(
            ctx=user,
            historical_temps=historical_temps,
            personalization=personalization,
        )

    return await run_alert_cycle(repo, messaging, score)


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
