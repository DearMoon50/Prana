"""Threshold robustness (sensitivity) analysis for the sleep-debt ledger.

The point: the ledger's exact constants (RECOVERY_PER_COOL_NIGHT_MIN=45,
RECOVERY_NIGHT_LOSS_THRESHOLD_MIN=5, the Minor-2022 dose-response anchors) were
adopted/chosen, not point-derived. This script defends them by showing the
model's *conclusion* is robust to them -- i.e. varying the recovery-rate
constants across their plausible range does NOT change what the ledger decides.

Core test = the discrimination claim (why the ledger exists): two households
with an identical COOL night tonight but different histories. A tonight-only
forecast treats them identically. Does the ledger keep separating them across
the whole grid?
"""
from __future__ import annotations

import importlib
from datetime import date, timedelta

from prana import config
from prana.recovery import ledger as ledger_mod
from prana.recovery.model import RecoveryModel

# Two households, identical cool tonight (30C), opposite histories.
_TODAY = date.today()
_HOT_HISTORY = [(3, 35.0), (2, 36.0), (1, 34.0), (0, 30.0)]
_COOL_HISTORY = [(3, 29.0), (2, 28.0), (1, 29.0), (0, 30.0)]


def _debt_mid(nights, per_cool_night, loss_threshold):
    """Compute debt_minutes_mid with monkeypatched ledger recovery constants."""
    old_per = config.RECOVERY_PER_COOL_NIGHT_MIN
    old_threshold = config.RECOVERY_NIGHT_LOSS_THRESHOLD_MIN
    config.RECOVERY_PER_COOL_NIGHT_MIN = per_cool_night
    config.RECOVERY_NIGHT_LOSS_THRESHOLD_MIN = loss_threshold
    importlib.reload(ledger_mod)  # ledger.py imports these constants at module load
    try:
        m = RecoveryModel()
        for days_ago, temp in nights:
            m.add_night_temperature(temp, _TODAY - timedelta(days=days_ago))
        return m.calculate_rds()["debt_minutes_mid"]
    finally:
        config.RECOVERY_PER_COOL_NIGHT_MIN = old_per
        config.RECOVERY_NIGHT_LOSS_THRESHOLD_MIN = old_threshold
        importlib.reload(ledger_mod)


def run() -> dict:
    per_cool_night_values = [30.0, 35.0, 40.0, 45.0, 50.0]
    # RECOVERY_NIGHT_LOSS_THRESHOLD_MIN is compared against minutes_lost() for
    # that night (default 5). Every night in both histories loses 9-35 min
    # (29C already loses 11.5, see dose_response anchors), so a threshold below
    # ~10 never lets ANY night recover in this scenario -- that's why a narrow
    # 3-7 sweep looked flat. Widen the range enough to cross into "some nights
    # now count as recovering" territory, so the sweep is actually exercised.
    loss_threshold_values = [5.0, 10.0, 15.0, 20.0, 25.0]

    print("=" * 70)
    print("SLEEP-DEBT LEDGER ROBUSTNESS -- discrimination test")
    print("Two households, both cool tonight (30C). A forecast calls both 'fine'.")
    print("Cell = debt_mid(hot-history) - debt_mid(cool-history), in minutes.")
    print("Positive = the ledger still separates them (the conclusion holds).")
    print("=" * 70)
    header = "thresh\\per " + "".join(f"{p:>8.0f}m" for p in per_cool_night_values)
    print(header)
    holds = 0
    total = 0
    min_gap = float("inf")
    for loss_threshold in loss_threshold_values:
        row = [f"  {loss_threshold:>4.0f}m  "]
        for per in per_cool_night_values:
            hot = _debt_mid(_HOT_HISTORY, per, loss_threshold)
            cool = _debt_mid(_COOL_HISTORY, per, loss_threshold)
            gap = hot - cool
            total += 1
            if gap > 0:
                holds += 1
            min_gap = min(min_gap, gap)
            row.append(f"{gap:>8.1f} ")
        print("".join(row))
    print("-" * 70)
    print(f"Discrimination holds in {holds}/{total} cells "
          f"(RECOVERY_PER_COOL_NIGHT_MIN 30-50min x RECOVERY_NIGHT_LOSS_THRESHOLD_MIN 5-25min).")
    print(f"Smallest separation anywhere in the grid: {min_gap:.1f} minutes.")
    print()
    print("Note on the dose-response anchors:")
    print("  - The Minor-2022 anchor curve sets the SHAPE of per-night loss, not")
    print("    whether hot nights cost more than cool ones -- it is monotonic by")
    print("    construction (see tests/recovery/test_dose_response.py), so it")
    print("    cannot flip which household is flagged.")
    print("  - RECOVERY_DEBT_CAP_MIN (240min) only bounds the ceiling; neither")
    print("    history in this test is anywhere near the cap, so it does not")
    print("    affect this comparison.")
    return {"holds": holds, "total": total, "min_gap": min_gap}


if __name__ == "__main__":
    run()
