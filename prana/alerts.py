"""Proactive climate-risk alerting.

An alert fires only when ALL hold:
  - risk level is risky (HIGH / CRITICAL / COMPOUND EMERGENCY),
  - the level CHANGED since the last recorded level (state-change semantics),
  - it has been at least ALERT_MIN_HOURS_BETWEEN since the last alert (daily cap),
  - the current local time is outside the quiet-hours window.
Non-risky levels are still recorded so a drop to SAFE then a rise re-alerts.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Awaitable, Callable, Optional

from framework.context.user import UserContext
from framework.messaging.registry import MessagingRegistry
from prana.config import (
    ALERT_MIN_HOURS_BETWEEN, ALERT_QUIET_HOURS_START, ALERT_QUIET_HOURS_END,
)

logger = logging.getLogger(__name__)

RISKY_LEVELS = frozenset({"HIGH", "CRITICAL", "COMPOUND EMERGENCY"})

RiskFn = Callable[[UserContext], Awaitable[dict]]


def _in_quiet_hours(now: datetime) -> bool:
    """Quiet hours wrap past midnight (e.g. 22:00–07:00)."""
    h = now.hour
    if ALERT_QUIET_HOURS_START <= ALERT_QUIET_HOURS_END:
        return ALERT_QUIET_HOURS_START <= h < ALERT_QUIET_HOURS_END
    return h >= ALERT_QUIET_HOURS_START or h < ALERT_QUIET_HOURS_END


def _hours_since(iso_ts: Optional[str], now: datetime) -> float:
    if not iso_ts:
        return float("inf")
    try:
        return (now - datetime.fromisoformat(iso_ts)).total_seconds() / 3600.0
    except ValueError:
        return float("inf")


async def check_and_alert_user(
    user: UserContext,
    risk_fn: RiskFn,
    repo,
    messaging: MessagingRegistry,
    now: Optional[datetime] = None,
) -> bool:
    """Score one user and send a WhatsApp alert if their risk turned dangerous,
    respecting the daily cap and quiet hours. Returns True iff an alert was sent."""
    now = now or datetime.now()
    try:
        risk = await risk_fn(user)
    except Exception:  # noqa: BLE001 - one user's failure must not stop the cycle
        logger.exception("Risk scoring failed for %s", user.phone)
        return False

    level = risk.get("risk_level")
    if risk.get("error") or level is None:
        return False

    last = user.metadata.get("last_alert_level")

    if last != level:
        user.metadata["last_alert_level"] = level
        await repo.upsert(user)

    if level not in RISKY_LEVELS or level == last:
        return False
    if _in_quiet_hours(now):
        return False
    if _hours_since(user.metadata.get("last_alert_at"), now) < ALERT_MIN_HOURS_BETWEEN:
        return False

    body = risk.get("alert_message") or f"PRANA alert: your climate risk is {level}."
    await messaging.send(channel="whatsapp", recipient=user.phone, body=body)
    user.metadata["last_alert_at"] = now.isoformat()
    await repo.upsert(user)
    logger.info("Sent %s alert to %s", level, user.phone)
    return True


async def run_alert_cycle(
    repo,
    messaging: MessagingRegistry,
    risk_fn: RiskFn,
) -> int:
    """Score every verified user and alert those whose risk turned dangerous."""
    users = await repo.list_all()
    sent = 0
    for user in users:
        if not user.metadata.get("verified"):
            continue
        if await check_and_alert_user(user, risk_fn, repo, messaging):
            sent += 1
    logger.info("Alert cycle complete: %d alert(s) sent across %d users", sent, len(users))
    return sent
