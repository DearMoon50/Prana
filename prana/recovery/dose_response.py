"""Per-night dose-response: effective indoor temperature -> minutes of sleep lost.

Continuous piecewise-linear curve anchored to Minor et al. 2022 (One Earth):
a night near 30C costs ~14 min of sleep, accelerating with heat. This replaces
the old 32C hard cliff and the un-fitted 10-pts/degC slope. Humidity is folded
in by nudging the effective temperature upward via the wet-bulb signal, so humid
nights are not underrated.
"""
import math
from prana.config import SLEEP_LOSS_ANCHORS, HOT_CLIMATE_SLEEP_MULTIPLIER, RDS_USE_WET_BULB
from prana.recovery.wetbulb import wet_bulb_stull


def _interp_anchor(temp) -> float:
    """Linear interpolation over SLEEP_LOSS_ANCHORS; flat outside the range."""
    anchors = SLEEP_LOSS_ANCHORS
    if temp <= anchors[0][0]:
        return anchors[0][1]
    if temp >= anchors[-1][0]:
        return anchors[-1][1]
    for (t0, m0), (t1, m1) in zip(anchors, anchors[1:]):
        if t0 <= temp <= t1:
            frac = (temp - t0) / (t1 - t0)
            return m0 + frac * (m1 - m0)
    return anchors[-1][1]  # unreachable, defensive


def _humidity_adjusted_temp(effective_temp, humidity) -> float:
    """Blend in humid-heat strain: use the hotter of dry-bulb effective temp and
    a wet-bulb-derived equivalent, so a humid night reads at least as hot as its
    dry-bulb number. Wet-bulb is shifted onto the dry-bulb comfort scale by the
    ~4C gap between the dry (32) and wet (28) thresholds."""
    if not RDS_USE_WET_BULB or humidity is None:
        return effective_temp
    wb = wet_bulb_stull(effective_temp, humidity)
    if wb is None:
        return effective_temp
    # 32C dry ~ 28C wet-bulb -> add the 4C offset to compare on one scale.
    wet_equiv = wb + 4.0
    return max(effective_temp, wet_equiv)


def minutes_lost(effective_temp, humidity=None, hot_climate=False) -> float:
    """Minutes of sleep lost for one night at the given effective indoor temp."""
    if effective_temp is None or not math.isfinite(float(effective_temp)):
        return 0.0
    t = _humidity_adjusted_temp(float(effective_temp), humidity)
    minutes = _interp_anchor(t)
    if hot_climate:
        minutes *= HOT_CLIMATE_SLEEP_MULTIPLIER
    return max(0.0, minutes)
