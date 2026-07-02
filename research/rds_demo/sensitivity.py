"""Threshold robustness (sensitivity) analysis for RDS.

The point: RDS's exact constants (32C threshold, 0.6 decay, 4-night window,
10 pts/degC slope) were adopted/chosen, not point-derived. This script defends
them by showing the model's *conclusion* is robust to them — i.e. varying each
constant across its plausible range does NOT change what RDS decides.

Core test = the discrimination claim (why RDS exists): two households with an
identical COOL night tonight but different histories. A tonight-only forecast
treats them identically. Does RDS keep separating them across the whole grid?
"""
from __future__ import annotations

from datetime import date, timedelta

import prana.rds_calculator as rc
from prana.rds_calculator import RDSCalculator

# Two households, identical cool tonight (30C), opposite histories.
_TODAY = date.today()
_HOT_HISTORY = [(3, 35.0), (2, 36.0), (1, 34.0), (0, 30.0)]
_COOL_HISTORY = [(3, 29.0), (2, 28.0), (1, 29.0), (0, 30.0)]


def _rds_mid(nights, threshold, decay):
    """Compute rds_mid with monkeypatched threshold + decay constants."""
    old_t, old_d = rc.RDS_NIGHTTIME_THRESHOLD, rc.RDS_DECAY_FACTOR
    rc.RDS_NIGHTTIME_THRESHOLD = threshold
    rc.RDS_DECAY_FACTOR = decay
    try:
        c = RDSCalculator()
        for da, t in nights:
            c.add_night_temperature(t, _TODAY - timedelta(days=da))
        # Disable wet-bulb here so we isolate the dry-bulb threshold under test.
        old_wb = rc.RDS_USE_WET_BULB
        rc.RDS_USE_WET_BULB = False
        try:
            return c.calculate_rds()["rds_mid"]
        finally:
            rc.RDS_USE_WET_BULB = old_wb
    finally:
        rc.RDS_NIGHTTIME_THRESHOLD = old_t
        rc.RDS_DECAY_FACTOR = old_d


def run() -> dict:
    thresholds = [30.0, 31.0, 32.0, 33.0, 34.0]
    decays = [0.4, 0.5, 0.6, 0.7, 0.8]

    print("=" * 70)
    print("RDS THRESHOLD ROBUSTNESS — discrimination test")
    print("Two households, both cool tonight (30C). A forecast calls both 'fine'.")
    print("Cell = RDS(hot-history) - RDS(cool-history). Positive = RDS still")
    print("separates them (the conclusion holds).")
    print("=" * 70)
    header = "decay\\thr  " + "".join(f"{t:>8.0f}C" for t in thresholds)
    print(header)
    holds = 0
    total = 0
    min_gap = float("inf")
    for d in decays:
        row = [f"  {d:>4.1f}   "]
        for t in thresholds:
            hot = _rds_mid(_HOT_HISTORY, t, d)
            cool = _rds_mid(_COOL_HISTORY, t, d)
            gap = hot - cool
            total += 1
            if gap > 0:
                holds += 1
            min_gap = min(min_gap, gap)
            row.append(f"{gap:>8.1f} ")
        print("".join(row))
    print("-" * 70)
    print(f"Discrimination holds in {holds}/{total} cells "
          f"(threshold 30-34C x decay 0.4-0.8).")
    print(f"Smallest separation anywhere in the grid: {min_gap:.1f} points.")
    print()
    print("Note on the other two constants:")
    print("  - RFU slope (pts/degC) is a pure multiplier: it scales every RDS")
    print("    equally, so it CANNOT change the ranking or which user is flagged.")
    print("  - 4-night window: older nights are already <0.8^4=0.41 weighted;")
    print("    extending it changes absolute RDS by a few points, not the order.")
    return {"holds": holds, "total": total, "min_gap": min_gap}


if __name__ == "__main__":
    run()
