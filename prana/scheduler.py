from __future__ import annotations

import asyncio
import logging

from prana.alerts import run_alert_cycle
from prana.ai_tools.risk import get_risk
from prana.bot.bootstrap import (
    build_messaging, build_repo, build_rds_repo, build_risk_eval_repo,
)
from prana.config import UPDATE_INTERVAL

logger = logging.getLogger(__name__)


async def _cycle_once() -> int:
    repo = build_repo()
    messaging = build_messaging()
    rds_repo = build_rds_repo()
    risk_eval_repo = build_risk_eval_repo()

    async def score(user):
        # We use get_risk which handles the calculation + self-loading of history.
        result = await get_risk(ctx=user)
        if "error" not in result:
            # Record the evaluation in history
            await risk_eval_repo.add(
                user.user_id,
                outdoor_temp=result.get("weather", {}).get("temp"),
                outdoor_humidity=result.get("weather", {}).get("humidity"),
                base_aqi=result.get("base_aqi"),
                ndt=result.get("ndt"),
                rds_mid=result.get("rds_mid"),
                ccri=result.get("ccri"),
            )
            # Persist updated RDS state so next cycle/app-open sees the new data
            if result.get("rds_historical_temps"):
                await rds_repo.save(user.user_id, result["rds_historical_temps"])
        return result

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
