"""Proactive climate-risk alerting.

A scheduler periodically scores every verified user and sends a WhatsApp alert
when their compound risk turns dangerous. To avoid spamming, an alert fires
only when the risk level is risky AND has *changed* since the last alert
(state-change semantics): a multi-day HIGH streak alerts once; a drop to safe
then a rise back to HIGH alerts again; an escalation HIGH->CRITICAL re-alerts.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from framework.context.user import UserContext
from framework.messaging.registry import MessagingRegistry

logger = logging.getLogger(__name__)

# Risk levels (from CCRICalculator.get_risk_level) that warrant a proactive
# alert. SAFE / ELEVATED do not.
RISKY_LEVELS = frozenset({"HIGH", "CRITICAL", "COMPOUND EMERGENCY"})

# A risk function maps a user to a scored-risk dict (same shape as get_risk):
# {"risk_level": str, "ccri": ..., "alert_message": str, ...}
RiskFn = Callable[[UserContext], dict]


async def check_and_alert_user(
    user: UserContext,
    risk_fn: RiskFn,
    repo,
    messaging: MessagingRegistry,
) -> bool:
    """Score one user and send a WhatsApp alert if their risk turned dangerous
    since the last alert. Returns True iff an alert was sent."""
    try:
        risk = risk_fn(user)
    except Exception:  # noqa: BLE001 - one user's failure must not stop the cycle
        logger.exception("Risk scoring failed for %s", user.phone)
        return False

    level = risk.get("risk_level")
    if risk.get("error") or level is None:
        return False

    last = user.metadata.get("last_alert_level")

    # Record the current level so escalations and re-alerts are detectable.
    # Non-risky levels are stored too (so dropping to SAFE then rising re-alerts).
    if user.metadata.get("last_alert_level") != level:
        user.metadata["last_alert_level"] = level
        await repo.upsert(user)

    if level in RISKY_LEVELS and level != last:
        body = risk.get("alert_message") or f"PRANA alert: your climate risk is {level}."
        await messaging.send(channel="whatsapp", recipient=user.phone, body=body)
        logger.info("Sent %s alert to %s", level, user.phone)
        return True
    return False


async def run_alert_cycle(
    repo,
    messaging: MessagingRegistry,
    risk_fn: RiskFn,
) -> int:
    """Score every verified user and alert those whose risk turned dangerous.
    Returns the number of alerts sent."""
    users = await repo.list_all()
    sent = 0
    for user in users:
        if not user.metadata.get("verified"):
            continue
        if await check_and_alert_user(user, risk_fn, repo, messaging):
            sent += 1
    logger.info("Alert cycle complete: %d alert(s) sent across %d users", sent, len(users))
    return sent
