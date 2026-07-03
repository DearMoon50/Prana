"""Chronological sleep-debt ledger.

debt_{n} = clamp(debt_{n-1} + lost_n - recovered_n, 0, CAP)

Recovery is bounded and physical (a cool night clears at most
RECOVERY_PER_COOL_NIGHT_MIN), and a night that itself cost sleep clears
proportionally less debt (you cannot recover on a night you slept badly). This
replaces the old 0.8^days_ago decay and the unitless 100 cap.
"""
from prana.config import RECOVERY_DEBT_CAP_MIN, RECOVERY_PER_COOL_NIGHT_MIN
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
        # A hot night clears little/no debt; a fully-cool night clears the most.
        # recovery fraction falls to 0 once a night's own loss reaches the
        # per-night recovery budget.
        recovery = max(0.0, RECOVERY_PER_COOL_NIGHT_MIN - lost)
        debt = debt + lost - recovery
        debt = max(0.0, min(RECOVERY_DEBT_CAP_MIN, debt))
    return debt
