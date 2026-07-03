"""Chronological sleep-debt ledger.

debt_{n} = clamp(debt_{n-1} + lost_n - recovered_n, 0, CAP)

Recovery is bounded, physical, and DECOUPLED from the loss curve: a night that
itself loses less than RECOVERY_NIGHT_LOSS_THRESHOLD_MIN (a genuinely cool,
recovering night) clears a fixed RECOVERY_PER_COOL_NIGHT_MIN of accumulated
debt; any hotter night clears nothing (you cannot recover on a night you slept
badly). This replaces the old 0.8^days_ago decay and the unitless 100 cap.

Why decoupled: an earlier draft used recovery = max(0, PER - lost), tying the
paydown rate to the same minutes scale as the loss. With PER=45 that zeroed out
all realistic debt (a 30C night loses 14 but "recovered" 45); dropping PER to
compensate would have silently shrunk the check-in bound (Task 9) and coupled
recovery speed to the anchor curve. A fixed paydown gated by a cool-night
threshold keeps the two knobs independent and meaningful.
"""
from prana.config import (
    RECOVERY_DEBT_CAP_MIN,
    RECOVERY_PER_COOL_NIGHT_MIN,
    RECOVERY_NIGHT_LOSS_THRESHOLD_MIN,
)
from prana.recovery.dose_response import minutes_lost


def accumulate_debt(nights) -> float:
    """Walk nights oldest-first, returning final carried debt in minutes.

    nights: list of {'effective_temp', 'humidity', 'hot_climate'} in
            chronological order (oldest first).
    """
    debt = 0.0
    for night in nights:
        lost = minutes_lost(
            night.get('effective_temp'),
            humidity=night.get('humidity'),
            hot_climate=night.get('hot_climate', False),
        )
        # Only a genuinely cool (recovering) night pays down debt, at a fixed
        # rate independent of the loss curve; a hot night clears nothing.
        recovery = RECOVERY_PER_COOL_NIGHT_MIN if lost < RECOVERY_NIGHT_LOSS_THRESHOLD_MIN else 0.0
        debt = debt + lost - recovery
        debt = max(0.0, min(RECOVERY_DEBT_CAP_MIN, debt))
    return debt
